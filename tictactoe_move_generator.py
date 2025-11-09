from pydantic import BaseModel
from typing import Dict, Optional
from copy import deepcopy
import json


class Vertex(BaseModel):
    size: list[int] = [3, 3, 1]
    state: Optional[list[str]] = None
    neighbors: set["Vertex"] = set()

    def __init__(self, **data):
        super().__init__(**data)
        if self.state is None:
            self.state = ["" for _ in range(self.size[0] * self.size[1] * self.size[2])]

    class Config:
        arbitrary_types_allowed = True

    def __hash__(self):
        return hash(tuple(self.state))
    
    def __eq(self, other):
        if not isinstance(other, Vertex):
            return False
        return self.state == other.state
    
    def to_dict(self) -> Dict:
        return {
            "state": self.state,
            "size": self.size,
            "is_terminal": self.is_winner("X") or self.is_winner("O") or self.is_full()
        }
    
    def is_winner(self, player: str) -> bool:
        l, w, h = self.size
        # Check rows
        for z in range(h):
            for y in range(w):
                for x in range(l-2):
                    if all(self.state[z*l*w + y*l + x+i] == player for i in range(3)):
                        return True
        
        # Check columns
        for z in range(h):
            for x in range(l):
                for y in range(w-2):
                    if all(self.state[z*l*w + (y+i)*l + x] == player for i in range(3)):
                        return True
                        
        # Check diagonals
        for z in range(h):
            for y in range(w-2):
                for x in range(l-2):
                    if all(self.state[z*l*w + (y+i)*l + x+i] == player for i in range(3)):
                        return True
                    if all(self.state[z*l*w + (y+i)*l + x+2-i] == player for i in range(3)):
                        return True
        
        return False

    def is_full(self) -> bool:
        return "" not in self.state


class Edge(BaseModel):
    vert1: Vertex = Vertex()
    vert2: Vertex = Vertex()
    move_position: int
    player: str

    def __hash__(self):
        return hash((hash(self.vert1), hash(self.vert2), self.move_position, self.player))
    
    def __eq__(self, other):
        if not isinstance(other, Edge):
            return False
        return (self.vert1 == other.vert1 and
                self.vert1 == other.vert2 and
                self.move_position == other.move_position and
                self.player == other.player)
    
    def to_dict(self) -> Dict:
        return {
            "from_state": self.vert1.state,
            "to_state": self.vert2.state,
            "move_position": self.move_position,
            "player": self.player
        }


class Graph(BaseModel):
    vertices: list[Vertex] = []
    edges: set[Edge] = set()

    def to_dict(self) -> Dict:
        # Find root vertex (one with no incoming edges)
        root = next(v for v in self.vertices 
                    if not any(e.vert2 == v for e in self.edges))

        # Simplified structure without paths
        return {
            "dimensions": root.size,
            "total_states": len(self.vertices),
            "total_moves": len(self.edges),
            "states": [v.to_dict() for v in self.vertices],
            "moves": [e.to_dict() for e in self.edges]
        }

    def get_vertex_by_state(self, state: list[str]) -> Optional[Vertex]:
        for vertex in self.vertices:
            if vertex.state == state:
                return vertex
        return None
    
    def gen_next_states(self, vertex: Vertex, player: str):
        # Find empty positions
        empty_positions = [i for i, val in enumerate(vertex.state) if val == ""]

        for pos in empty_positions:
            # Create new state
            new_state = deepcopy(vertex.state)
            new_state[pos] = player

            # Check if this state already exists
            existing_vertex = self.get_vertex_by_state(new_state)

            if existing_vertex is None:
                # Create new vertex
                new_vertex = Vertex(size=vertex.size, state=new_state)
                self.vertices.append(new_vertex)
                existing_vertex = new_vertex

            # Create edge
            new_edge = Edge(
                vert1 = vertex,
                vert2 = existing_vertex,
                move_position = pos,
                player = player
            )
            self.edges.add(new_edge)

            # Add to vertex's neighbors
            vertex.neighbors.add(existing_vertex)

            if len(existing_vertex.neighbors) == 0:
                vertex.neighbors.add(existing_vertex)

                # If game isn't over, generate next moves for opponent
                if not existing_vertex.is_winner(player) and not existing_vertex.is_full():
                    self.gen_next_states(existing_vertex, "O" if player == "X" else "X")


def create_game_tree(game_dict):
    def find_parent_state(state_list):
        # Convert state list to string for easier comparison
        state = ''.join(state_list)
        x_count = state.count('X')
        o_count = state.count('O')
        
        # Find last move position
        diff_positions = []
        for i, char in enumerate(state_list):
            if char in ['X', 'O']:
                diff_positions.append(i)
                
        if len(diff_positions) > 0:
            parent_state = state_list.copy()
            parent_state[diff_positions[-1]] = ''
            return parent_state
        return None

    # Create tree structure
    tree = {}
    
    # Sort states by number of moves
    sorted_states = sorted(
        game_dict['states'], 
        key=lambda x: x['state'].count('X') + x['state'].count('O')
    )
    
    for state_data in sorted_states:
        current_node = {
            "state": state_data['state'],
            "is_terminal": state_data['is_terminal'],
            "children": []
        }
        
        parent_state = find_parent_state(state_data['state'])
        
        if parent_state is None:
            # This is the root
            tree['root'] = current_node
        else:
            # Find parent node
            def find_node_with_state(node, target_state):
                if node['state'] == target_state:
                    return node
                for child in node.get('children', []):
                    result = find_node_with_state(child, target_state)
                    if result:
                        return result
                return None

            parent_node = find_node_with_state(tree['root'], parent_state)
            if parent_node:
                parent_node['children'].append(current_node)

    return tree


def main():
    import sys

    l = int(sys.argv[1])
    w = int(sys.argv[2])
    h = int(sys.argv[3])

    board = Graph()
    root = Vertex(size=[l, w, h])
    board.vertices.append(root)

    # Generate all possible games states starting with X
    board.gen_next_states(root, "X")

    print(f"Generated {len(board.vertices)} states!")
    print(f"Generated {len(board.edges)} moves!")

    output_file = f"tictactoe_{l}x{w}x{h}.json"
    with open(output_file, "w") as f:
        json.dump(create_game_tree(board.to_dict()), f, indent=2)
    print(f"Game tree saved to {output_file}") 
     
           


if __name__ == "__main__":
    main()
