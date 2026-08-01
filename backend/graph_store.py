import re

class KnowledgeGraph:
    def __init__(self):
        # nodes format: {node_id: { "type": type, "label": label, "properties": {} }}
        self.nodes = {}
        # edges format: {node_id: [ {"target": target_id, "type": rel_type, "properties": {}} ]}
        self.edges = {}

    def add_node(self, node_id, node_type, label, properties=None):
        self.nodes[node_id] = {
            "type": node_type,
            "label": label,
            "properties": properties or {}
        }
        if node_id not in self.edges:
            self.edges[node_id] = []

    def add_edge(self, source, target, rel_type, properties=None):
        if source not in self.nodes or target not in self.nodes:
            # Create placeholder nodes if they don't exist
            if source not in self.nodes:
                self.add_node(source, "Unknown", source)
            if target not in self.nodes:
                self.add_node(target, "Unknown", target)
                
        self.edges[source].append({
            "target": target,
            "type": rel_type,
            "properties": properties or {}
        })

    def get_neighbors(self, node_id):
        return self.edges.get(node_id, [])

    def to_json(self):
        """Returns the Vis.js compatible graph format (nodes and edges lists)."""
        nodes_list = []
        for n_id, n_data in self.nodes.items():
            nodes_list.append({
                "id": n_id,
                "label": n_data["label"],
                "group": n_data["type"],
                "properties": n_data["properties"]
            })
            
        edges_list = []
        for src, rels in self.edges.items():
            for r in rels:
                edges_list.append({
                    "from": src,
                    "to": r["target"],
                    "label": r["type"]
                })
        return {"nodes": nodes_list, "edges": edges_list}

def build_knowledge_graph(df_vehicles, df_maintenance, df_warranty):
    """
    Constructs the operational Fleet Knowledge Graph.
    """
    kg = KnowledgeGraph()
    
    # 1. Add Components (Standard fleet breakdown)
    components = {
        "Engine": "Heavy Duty Drivetrain Engine Assembly",
        "Cooling System": "Radiator, Thermostat, and EGR Cooling Core",
        "Turbocharger": "Variable Geometry Turbo and Compressor",
        "Electrical": "Alternator, Battery Banks, and Starter Motor",
        "Fuel Injector": "High Pressure Common Rail Injectors"
    }
    
    for comp, desc in components.items():
        kg.add_node(comp, "Component", comp, {"description": desc})
        
    # 2. Add Fault Codes
    fault_codes = {
        "P0128": {"label": "P0128: Coolant Temp Below Threshold", "component": "Cooling System"},
        "P0299": {"label": "P0299: Turbocharger Underboost", "component": "Turbocharger"},
        "P0562": {"label": "P0562: Alternator System Voltage Low", "component": "Electrical"},
        "P0300": {"label": "P0300: Engine Misfire Detected", "component": "Engine"},
        "P026A": {"label": "P026A: Charge Air Cooler Efficiency Low", "component": "Turbocharger"}
    }
    for code, info in fault_codes.items():
        kg.add_node(code, "FaultCode", info["label"], {"description": info["label"]})
        kg.add_edge(code, info["component"], "INDICATES_FAULT_IN")

    # 3. Add Vehicles and connect to Components
    for _, row in df_vehicles.iterrows():
        v_id = row["id"]
        kg.add_node(v_id, "Vehicle", f"{row['manufacturer']} {v_id}", {
            "manufacturer": row["manufacturer"],
            "model": row["model"],
            "year": int(row["year"]),
            "status": row.get("status", row.get("initial_status", "Healthy"))
        })
        
        # Connect vehicles to standard components
        for comp in components:
            kg.add_edge(v_id, comp, "HAS_COMPONENT")

    # 4. Add Maintenance Logs and connect to Vehicle & Component
    for _, row in df_maintenance.iterrows():
        m_id = row["id"]
        kg.add_node(m_id, "Maintenance", f"Repair {m_id}", {
            "date": row["date"],
            "component": row["component"],
            "description": row["description"],
            "cost": float(row["cost"])
        })
        
        # Connect Maintenance to Vehicle
        kg.add_edge(m_id, row["vehicle_id"], "PERFORMED_ON")
        
        # Map description keywords to components to link maintenance to component
        mapped = False
        for comp in components:
            if comp.lower() in row["component"].lower() or comp.lower() in row["description"].lower():
                kg.add_edge(m_id, comp, "RESOLVED_ISSUE_FOR")
                mapped = True
        if not mapped:
            kg.add_edge(m_id, "Engine", "RESOLVED_ISSUE_FOR") # Fallback default

    # 5. Add Warranty Claims and connect to Vehicle & Component
    for _, row in df_warranty.iterrows():
        w_id = row["id"]
        kg.add_node(w_id, "Warranty", f"Claim {w_id}", {
            "component": row["component"],
            "claim_date": row["claim_date"],
            "cost": float(row["cost"]),
            "status": row["status"]
        })
        
        kg.add_edge(w_id, row["vehicle_id"], "FILED_BY")
        
        # Connect to parent Component
        for comp in components:
            if comp.lower() in row["component"].lower():
                kg.add_edge(w_id, comp, "COVERS_COMPONENT")

    # 6. Specific Fault injections on KG for failing vehicles
    # TRK-427 cooling system has cooling failure fault
    kg.add_edge("TRK-427", "P0128", "TRIGGERED")
    kg.add_edge("TRK-427", "P0300", "TRIGGERED")
    
    # TRK-454 turbo has underboost fault
    kg.add_edge("TRK-454", "P0299", "TRIGGERED")
    kg.add_edge("TRK-454", "P026A", "TRIGGERED")
    
    # TRK-481 electrical system has voltage low fault
    kg.add_edge("TRK-481", "P0562", "TRIGGERED")
    
    return kg

class GraphRAGPipeline:
    def __init__(self, kg):
        self.kg = kg
        
    def entity_linking(self, query):
        """
        Parses query to extract node references.
        Uses regex and vocabulary lookup.
        """
        linked_entities = []
        q_lower = query.lower()
        
        # Match vehicle pattern: TRK-\d+
        vehicles_found = re.findall(r"trk-\d+", q_lower)
        for v in vehicles_found:
            v_upper = v.upper()
            if v_upper in self.kg.nodes:
                linked_entities.append(v_upper)
                
        # Match fault codes: P\d+[A-Z]?
        faults_found = re.findall(r"p\d+[a-z]?", q_lower)
        for f in faults_found:
            f_upper = f.upper()
            if f_upper in self.kg.nodes:
                linked_entities.append(f_upper)
                
        # Match components keywords
        components_voc = ["engine", "cooling system", "turbocharger", "electrical", "fuel injector"]
        for c in components_voc:
            if c in q_lower:
                # Find exact matching node name case-sensitively
                for node_id, data in self.kg.nodes.items():
                    if data["type"] == "Component" and node_id.lower() == c:
                        linked_entities.append(node_id)
                        
        # Match manufacturer keywords
        mfrs = ["volvo", "freightliner", "kenworth", "peterbilt", "mack"]
        for m in mfrs:
            if m in q_lower:
                # Find vehicles of this manufacturer
                for v_id, data in self.kg.nodes.items():
                    if data["type"] == "Vehicle" and data["properties"].get("manufacturer", "").lower() == m:
                        linked_entities.append(v_id)
                        
        return list(set(linked_entities))

    def extract_subgraph(self, entities, max_nodes=20):
        """
        Extracts subgraph (1-hop and 2-hop neighbor expansion) for query entities.
        Compresses relationships into structural text facts.
        """
        subgraph_nodes = set(entities)
        subgraph_edges = []
        
        # 1. Neighbor expansion (1-hop)
        for ent in entities:
            neighbors = self.kg.get_neighbors(ent)
            for r in neighbors:
                subgraph_nodes.add(r["target"])
                subgraph_edges.append((ent, r["target"], r["type"]))
                
            # Check reverse relations (other nodes pointing to this entity)
            for src, rels in self.kg.edges.items():
                for r in rels:
                    if r["target"] == ent:
                        subgraph_nodes.add(src)
                        subgraph_edges.append((src, ent, r["type"]))
                        
        # 2. Expanding 2-hop for high importance entities (Vehicles and FaultCodes)
        for ent in list(subgraph_nodes):
            if ent in self.kg.nodes:
                etype = self.kg.nodes[ent]["type"]
                if etype in ["Vehicle", "FaultCode"]:
                    neighbors = self.kg.get_neighbors(ent)
                    for r in neighbors:
                        if len(subgraph_nodes) < max_nodes:
                            subgraph_nodes.add(r["target"])
                            subgraph_edges.append((ent, r["target"], r["type"]))
                            
        # Filter duplicates in edges
        unique_edges = list(set(subgraph_edges))
        
        # 3. Context Compression: Formulate clean sentences
        facts = []
        for src, dest, rel in unique_edges:
            src_lbl = self.kg.nodes[src]["label"] if src in self.kg.nodes else src
            dest_lbl = self.kg.nodes[dest]["label"] if dest in self.kg.nodes else dest
            src_type = self.kg.nodes[src]["type"] if src in self.kg.nodes else "Unknown"
            dest_type = self.kg.nodes[dest]["type"] if dest in self.kg.nodes else "Unknown"
            
            # Print properties if they add value
            props_str = ""
            if src_type == "Maintenance":
                props = self.kg.nodes[src]["properties"]
                props_str = f" (Date: {props.get('date')}, Desc: {props.get('description')}, Cost: ${props.get('cost')})"
            elif src_type == "Warranty":
                props = self.kg.nodes[src]["properties"]
                props_str = f" (Date: {props.get('claim_date')}, Status: {props.get('status')}, Cost: ${props.get('cost')})"
                
            facts.append(f"- [{src_type}] {src_lbl} --({rel})--> [{dest_type}] {dest_lbl}{props_str}")
            
        return {
            "nodes": list(subgraph_nodes),
            "edges": unique_edges,
            "serialized_facts": "\n".join(facts) if facts else "No KG associations found."
        }
