from postprocessors.Check import Check
import numpy as np

class SuperpositionCheck(Check):
    def __init__(self, base_feature, secondary_feature, config):
        super().__init__()
        self.base_feature = base_feature
        self.secondary_feature = secondary_feature

        self.base_feature_type_id = config.nodes_type_id[self.base_feature]
        self.secondary_feature_type_id = config.nodes_type_id[self.secondary_feature]

        self.connections = {}
        self.nodes = {}
        self.connection_error = {} 

    # Space for auxiliary functions specific to this class.

    def add_error(self, base_element, super_element):
        if not self.connection_error.get(base_element):
            self.connection_error[base_element] = set()
        self.connection_error[base_element].add(super_element)

    def make_errors(self):
        for base, secondaries in self.connection_error.items():
            self.errors.append(f"El elemento {base} del tipo {self.base_feature} no está conectado a los elementos {secondaries} de tipo {self.secondary_feature}.")

    def set_connection(self, base_info, secondary_info):
        if self.connections.get(base_info["name"]):
            self.connections[base_info["name"]].append(secondary_info["name"])
        else:
            self.connections[base_info["name"]] = [secondary_info["name"]]

    def check_connection(self, base_name, secondary_name):
        if self.connections.get(base_name):
            return secondary_name in self.connections[base_name]
        
        # not sure, aquí manejo el error de si algo no existe en la lista de conexiones.
        return True

    def make_connection_matrix(self):
            base_labels = []
            secondary_labels = []
            for base, secondaries in self.connections.items():
                base_labels.append(base)
                for secondary in secondaries:
                    if secondary not in secondary_labels:
                        secondary_labels.append(secondary)
            
            matrix = np.zeros((len(base_labels), len(secondary_labels)), dtype=float)

            for i, base in enumerate(base_labels):
                for j, secondary in enumerate(secondary_labels):
                    if secondary in self.connections[base]:
                        matrix[i][j] = 1
            
            # Add the errors in red
            for base, secondaries in self.connection_error.items():

                i = base_labels.index(base)
                for secondary in secondaries:
                    j = secondary_labels.index(secondary)
                    matrix[i][j] = 0.5

            # this made a simple connection matrix
            return matrix, base_labels, secondary_labels


    # We use a structure to save the connections between nodes.
    # We use another one to save a translation between the node ID and the node name.

    def get_name(self):
        return f"Superposition check between {self.base_feature} and {self.secondary_feature}"
    
    def get_description(self):
        return "Check if the base feature is superposed with the secondary feature."

    def plot(self, visualizator):
        matrix, base_labels, secondary_labels= self.make_connection_matrix()
        visualizator.write_matrix_img(matrix, "superposition_matrix_"+self.base_feature+"_"+self.secondary_feature,
                                       base_labels, secondary_labels, cmap='rocket', linewidth=0.5)

    def arc_init_operation(self, arc_id, arc):
        pass

    def node_init_operation(self, node_id, node):
        type_id = node['type_id']
        if type_id == self.base_feature_type_id or type_id == self.secondary_feature_type_id:
            self.nodes[node_id] = node

    def cell_init_operation(self, cell_id, cell):
        pass

    def arc_check_operation(self, arc_id, arc):
        src_id = arc["src_id"]
        dst_id = arc["dst_id"]

        if (src_id and dst_id) and (src_id in self.nodes and dst_id in self.nodes):
            if self.nodes[src_id]["type_id"] == self.base_feature_type_id and self.nodes[dst_id]["type_id"] == self.secondary_feature_type_id:
                self.set_connection(self.nodes[src_id], self.nodes[dst_id])
            elif self.nodes[src_id]["type_id"] == self.secondary_feature_type_id and self.nodes[dst_id]["type_id"] == self.base_feature_type_id:
                self.set_connection(self.nodes[dst_id], self.nodes[src_id])

    def node_check_operation(self, node_id, node):
        pass

    def cell_check_operation(self, cell_id, cell):
        base_element = self.get_cell_feature_names(cell, self.base_feature)
        secondary_element = self.get_cell_feature_names(cell, self.secondary_feature)

        for base_name in base_element:
            for secondary_name in secondary_element:
                if not self.check_connection(base_name, secondary_name):
                    self.add_error(base_name, secondary_name)
        
        self.make_errors()
        
                    

