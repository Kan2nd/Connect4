import socket
import threading
import pickle
import sys
import random

class Connect4GameServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server_socket = None
        self.clients = {}  # Dictionary to store client sockets by username
        self.rooms = {}   # Dictionary to store room names and their users
        self.ready_players = {}  # Track ready status per room: {room_name: {username: ready_status}}
        self.max_rooms = 4  # Maximum number of rooms allowed
        self.game_running_status = {}  # Track game running state per room
        self.player_assignments = {}  # Track player number assignments per room: {room_name: {username: player_number}}
        self.game_boards = {}  # Track game board state per room
        self.current_turns = {}  # Track whose turn it is per room
        self.init_server()

    def init_server(self):
        """Initialize the server socket and start listening for connections."""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"🔴 Connect 4 Game Server started on {self.host}:{self.port}")
            print(f"📋 Maximum rooms allowed: {self.max_rooms}")
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            sys.exit(1)

        # Start accepting client connections
        threading.Thread(target=self.accept_connections).start()

    def accept_connections(self):
        """Accept incoming client connections in a separate thread."""
        while True:
            try:
                client_socket, addr = self.server_socket.accept()
                print(f"🌐 New player connection from {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket, addr)).start()
            except Exception as e:
                print(f"❌ Error accepting connection: {e}")

    def assign_random_players(self, room_name):
        """Randomly assign player numbers (1 or 2) to players in the room."""
        if room_name not in self.rooms or len(self.rooms[room_name]) < 2:
            return {}
        
        players = self.rooms[room_name].copy()
        random.shuffle(players)  # Randomize the order
        
        # Assign player 1 and 2 randomly
        assignment = {
            players[0]: 1,
            players[1]: 2
        }
        
        self.player_assignments[room_name] = assignment
        print(f"🎲 Random player assignment for room {room_name}: {assignment}")
        return assignment

    def initialize_game_board(self, room_name):
        """Initialize a new game board for the room."""
        # Connect 4 board: 6 rows x 7 columns, all empty (0)
        self.game_boards[room_name] = [[0 for _ in range(7)] for _ in range(6)]
        self.current_turns[room_name] = 1  # Player 1 always starts
        print(f"🎮 Initialized game board for room {room_name}")

    def handle_client(self, client_socket, addr):
        """Handle communication with a connected client."""
        username = None
        while True:
            try:
                # Receiving data from client
                data = client_socket.recv(1048576)
                if not data:
                    print(f"🔌 Player {addr} disconnected")
                    break
                message = pickle.loads(data)
                if not message:
                    continue
                print(f"📨 Received from {addr}: {message}")
                
                # Process client commands
                if message["Command"] == "Check_Username":
                    username = message["User_Name"]
                    # Always treat username as valid and add client
                    self.clients[username] = client_socket
                    response = {
                        "Command": "Check_Username",
                        "Status": "Valid",
                        "Users_In_Room": [] # List of  users in the room (empty for now since we are not in any room)
                    }
                    self.send_message(client_socket, response)
                    self.broadcast_room_state()
                    print(f"✅ Player {username} registered successfully")

                elif message["Command"] == "Request_Room_State":
                    self.send_message(client_socket, {
                        "Command": "Room_State",
                        "Available_Rooms": list(self.rooms.keys()),
                        "Users_In_Room": self.rooms.get(message.get("Room_Name", ""), [])
                    })
                    
                elif message["Command"] == "Create_Room":
                    room_name = message["Room_Name"]
                    username = message["User_Name"]
                    
                    # Check room limit
                    if len(self.rooms) >= self.max_rooms:
                        print(f"🚫 Room creation denied - maximum {self.max_rooms} rooms reached")
                        continue
                        
                    print(f"🏗️ Creating room {room_name} for player {username}")
                    self.create_room(room_name, username)
                    self.broadcast_room_state()

                elif message["Command"] == "Join_Room":
                    room_name = message["Room_Name"]
                    username = message["User_Name"]
                    
                    # Check if room already has 2 players (Connect 4 limit)
                    if room_name in self.rooms and len(self.rooms[room_name]) >= 2:
                        print(f"🚫 Player {username} cannot join room {room_name} - room is full (2/2 players)")
                        continue
                    
                    print(f"🚪 Player {username} joining room {room_name}")
                    self.join_room(room_name, username)
                    
                    # Initialize ready status for new player
                    if room_name not in self.ready_players:
                        self.ready_players[room_name] = {}
                    self.ready_players[room_name][username] = False
                    
                    response = {
                        "Command": "Join_Room",
                        "Room_Name": room_name,
                        "User_Name": username,
                        "Users_In_Room": self.rooms.get(room_name, [])
                    }
                    self.broadcast_to_room(room_name, response)
                    
                    # Broadcast updated room state
                    self.broadcast_to_room(room_name, {
                        "Command": "Room_State",
                        "Available_Rooms": list(self.rooms.keys()),
                        "Users_In_Room": self.rooms.get(room_name, [])
                    })
                    
                    self.broadcast_to_room(room_name, {
                        "Command": "Sending_Message",
                        "Room_Name": room_name,
                        "User_Name": username,
                        "Text": f"{username} has joined the game!"
                    })

                elif message["Command"] == "Player_Ready":
                    room_name = message["Room_Name"]
                    username = message["User_Name"]
                    ready_status = message["Ready_Status"]
                    
                    # Don't process ready changes during game
                    if room_name in self.game_running_status and self.game_running_status[room_name]:
                        print(f"🚫 Player {username} tried to change ready status while game is running")
                        continue
                        
                    print(f"⚡ Player {username} in room {room_name} is now {ready_status}")
                    # Update ready status
                    if room_name in self.ready_players:
                        self.ready_players[room_name][username] = (ready_status == "READY")
                    
                    # Broadcast ready status to all players in room
                    self.broadcast_to_room(room_name, {
                        "Command": "Player_Ready",
                        "Room_Name": room_name,
                        "User_Name": username,
                        "Ready_Status": ready_status
                    })
                    
                    # Check if both players are ready to auto-start Connect 4
                    self.check_auto_start_game(room_name)

                elif message["Command"] == "Auto_Start_Game":
                    room_name = message["Room_Name"]
                    username = message["User_Name"]
                    
                    print(f"🎮 Auto-starting Connect 4 game in room {room_name}")
                    
                    # Check if room exists and has exactly 2 players
                    if room_name in self.rooms and len(self.rooms[room_name]) == 2:
                        # Set game as running FIRST
                        self.game_running_status[room_name] = True
                        
                        # Create random player assignments BEFORE starting game
                        player_assignment = self.assign_random_players(room_name)
                        
                        # Initialize game board and turn tracking
                        self.initialize_game_board(room_name)
                        
                        # Broadcast game start with player assignments
                        self.broadcast_to_room(room_name, {
                            "Command": "Game_Started",
                            "Room_Name": room_name,
                            "User_Name": username,
                            "Player_Assignment": player_assignment
                        })
                        print(f"✅ Connect 4 game auto-started in room {room_name} with players: {self.rooms[room_name]}")
                        print(f"🎲 Player assignments: {player_assignment}")
                    else:
                        print(f"🚫 Cannot auto-start Connect 4 game in room {room_name} - need exactly 2 players")
                        
                elif message["Command"] == "Sending_Message":
                    room_name = message["Room_Name"]
                    username = message["User_Name"]
                    text = message["Text"]
                    
                    # Handle leave message
                    leave_text = f"{username} has left the room."
                    if text == leave_text and room_name in self.rooms:
                        if username in self.rooms[room_name]:
                            #Removing the user from the room
                            self.rooms[room_name].remove(username)
                            print(f"👋 Removed {username} from room {room_name}")
                            
                            # Remove ready players
                            if room_name in self.ready_players and username in self.ready_players[room_name]:
                                del self.ready_players[room_name][username]
                            
                            # Clean up game data
                            if room_name in self.player_assignments and username in self.player_assignments[room_name]:
                                del self.player_assignments[room_name][username]
                            
                            # If room is empty, delete it
                            if not self.rooms[room_name]:
                                del self.rooms[room_name]
                                if room_name in self.ready_players:
                                    del self.ready_players[room_name]
                                if room_name in self.game_running_status:
                                    del self.game_running_status[room_name]
                                if room_name in self.player_assignments:
                                    del self.player_assignments[room_name]
                                if room_name in self.game_boards:
                                    del self.game_boards[room_name]
                                if room_name in self.current_turns:
                                    del self.current_turns[room_name]
                                print(f"🗑️ Deleted empty room {room_name}")
                                self.broadcast_room_state()
                            else:
                                # Send updated user list and room state to room
                                self.broadcast_to_room(room_name, {
                                    "Command": "Room_State",
                                    "Available_Rooms": list(self.rooms.keys()),
                                    "Users_In_Room": self.rooms[room_name]
                                })
                                self.broadcast_to_room(room_name, {
                                    "Command": "Sending_Message",
                                    "Room_Name": room_name,
                                    "User_Name": username,
                                    "Text": text
                                })
                    else:
                        self.broadcast_room_state()
                        self.broadcast_to_room(room_name, {
                            "Command": "Sending_Message",
                            "Room_Name": room_name,
                            "User_Name": username,
                            "Text": text
                        })
                    
                elif message["Command"] == "Game_State_Update":
                    room_name = message["Room_Name"]
                    username = message["User_Name"]
                    game_running = message["Game_Running"]
                    print(f"🎮 Game state update for room {room_name}: {game_running}")                    
                    
                    # Update server's game running state
                    self.game_running_status[room_name] = game_running
                    
                    if not game_running:  # Game ended
                        print(f"🔄 Connect 4 game ended in room {room_name}, resetting all players to NOT READY")
                        # Reset all ready states for this room
                        if room_name in self.ready_players:
                            for player in self.ready_players[room_name]:
                                self.ready_players[room_name][player] = False
                        
                        # Clear game data
                        if room_name in self.player_assignments:
                            del self.player_assignments[room_name]
                        if room_name in self.game_boards:
                            del self.game_boards[room_name]
                        if room_name in self.current_turns:
                            del self.current_turns[room_name]
                            
                        # Broadcast ready state reset to all players in room
                        if room_name in self.rooms:
                            for player in self.rooms[room_name]:
                                self.broadcast_to_room(room_name, {
                                    "Command": "Player_Ready",
                                    "Room_Name": room_name,
                                    "User_Name": player,
                                    "Ready_Status": "NOT_READY"
                                })
                                
                    # Broadcast game state update to all players in room
                    self.broadcast_to_room(room_name, {
                        "Command": "Game_State_Update",
                        "Room_Name": room_name,
                        "User_Name": username,
                        "Game_Running": game_running
                    })
                    print(f"🔄 Game state updated for room {room_name}: {game_running}")
                    
                # Handle Connect 4 game messages
                elif message["Command"] == "game_move":
                    room_name = message["room_name"]
                    username = message["username"]
                    col = message["col"]
                    player = message["player"]
                    print(f"🔴 Connect 4 move from {username} in room {room_name}: column {col}, player {player}")
                    
                    # Validate turn (server-side turn management)
                    if room_name in self.current_turns and room_name in self.player_assignments:
                        expected_player = self.current_turns[room_name]
                        if self.player_assignments[room_name].get(username) != expected_player:
                            print(f"🚫 Invalid turn: {username} tried to play but it's player {expected_player}'s turn")
                            # Send turn update to remind client whose turn it is
                            self.broadcast_to_room(room_name, {
                                "Command": "turn_update",
                                "room_name": room_name,
                                "current_player": expected_player
                            })
                            continue
                    
                    # Validate and apply move to server board
                    if self.validate_and_apply_move(room_name, col, player):
                        # Switch turns
                        if room_name in self.current_turns:
                            self.current_turns[room_name] = 2 if self.current_turns[room_name] == 1 else 1
                        
                        # Broadcast move to all players in room
                        self.broadcast_to_room(room_name, {
                            "Command": "game_move",
                            "room_name": room_name,
                            "username": username,
                            "col": col,
                            "player": player
                        })
                        
                        # Broadcast turn update
                        if room_name in self.current_turns:
                            self.broadcast_to_room(room_name, {
                                "Command": "turn_update",
                                "room_name": room_name,
                                "current_player": self.current_turns[room_name]
                            })
                    else:
                        print(f"🚫 Invalid move from {username} in room {room_name}: column {col}")
                    
                elif message["Command"] == "game_reset":
                    room_name = message["room_name"]
                    username = message["username"]
                    print(f"🔄 Connect 4 game reset from {username} in room {room_name}")
                    
                    # Reset game board and turn
                    self.initialize_game_board(room_name)
                    
                    # Broadcast game reset to all players in room
                    self.broadcast_to_room(room_name, {
                        "Command": "game_reset",
                        "room_name": room_name,
                        "username": username
                    })
                elif message["Command"] == "player_left_game":
                    room_name = message["room_name"]
                    username = message["username"]
                    print(f"🚪 Player {username} left the Connect 4 game in room {room_name}")
                    
                    # Set game as not running
                    self.game_running_status[room_name] = False
                    
                    # Clear game data
                    if room_name in self.player_assignments:
                        del self.player_assignments[room_name]
                    if room_name in self.game_boards:
                        del self.game_boards[room_name]
                    if room_name in self.current_turns:
                        del self.current_turns[room_name]
                    
                    # Reset ready status for all players
                    if room_name in self.ready_players:
                        for player in self.ready_players[room_name]:
                            self.ready_players[room_name][player] = False
                    
                    # Determine winner (the player who didn't leave)
                    winner = None
                    if room_name in self.rooms:
                        for player in self.rooms[room_name]:
                            if player != username:
                                winner = player
                                break
                    
                    # Broadcast game end with winner to all players in room
                    self.broadcast_to_room(room_name, {
                        "Command": "game_ended_player_left",
                        "room_name": room_name,
                        "left_player": username,
                        "winner": winner
                    })
                    
                    # Broadcast ready state reset to all players in room
                    if room_name in self.rooms:
                        for player in self.rooms[room_name]:
                            self.broadcast_to_room(room_name, {
                                "Command": "Player_Ready",
                                "Room_Name": room_name,
                                "User_Name": player,
                                "Ready_Status": "NOT_READY"
                            })   
            except Exception as e:
                print(f"❌ Error handling client {addr}: {e}")
                break

        # Cleanup when client disconnects
        if username and username in self.clients:
            print(f"🧹 Cleaning up for disconnected player {username}")
            del self.clients[username]
            for room_name, users in list(self.rooms.items()):
                if username in users:
                    users.remove(username)
                    
                    # Remove from ready players
                    if room_name in self.ready_players and username in self.ready_players[room_name]:
                        del self.ready_players[room_name][username]
                    
                    # Clean up game data
                    if room_name in self.player_assignments and username in self.player_assignments[room_name]:
                        del self.player_assignments[room_name][username]
                    
                    if not users:
                        del self.rooms[room_name]
                        if room_name in self.ready_players:
                            del self.ready_players[room_name]
                        if room_name in self.game_running_status:
                            del self.game_running_status[room_name]
                        if room_name in self.player_assignments:
                            del self.player_assignments[room_name]
                        if room_name in self.game_boards:
                            del self.game_boards[room_name]
                        if room_name in self.current_turns:
                            del self.current_turns[room_name]
                        print(f"🗑️ Deleted empty room {room_name}")
                        self.broadcast_room_state()
                    else:
                        # Notify remaining players about disconnect
                        self.broadcast_to_room(room_name, {
                            "Command": "player_disconnect",
                            "username": username,
                            "room_name": room_name
                        })
                        
                        self.broadcast_to_room(room_name, {
                            "Command": "Join_Room",
                            "Room_Name": room_name,
                            "User_Name": username,
                            "Users_In_Room": users
                        })
                        
                        self.broadcast_to_room(room_name, {
                            "Command": "Room_State",
                            "Available_Rooms": list(self.rooms.keys()),
                            "Users_In_Room": users
                        })
            if self.rooms:
                self.broadcast_room_state()
        try:
            client_socket.close()
        except:
            pass

    def validate_and_apply_move(self, room_name, col, player):
        """Validate and apply a move to the server's game board."""
        if room_name not in self.game_boards:
            return False
        
        board = self.game_boards[room_name]
        
        # Check if column is valid and not full
        if not (0 <= col < 7) or board[0][col] != 0:
            return False
        
        # Find the lowest empty row in the column
        for row in range(5, -1, -1):  # 6 rows (0-5), check from bottom
            if board[row][col] == 0:
                board[row][col] = player
                print(f"✅ Applied move: Player {player} to column {col}, row {row} in room {room_name}")
                return True
        
        return False

    def check_auto_start_game(self, room_name):
        """Check if both players in a Connect 4 room are ready to auto-start the game."""
        if room_name not in self.ready_players or room_name not in self.rooms:
            return
        if room_name in self.game_running_status and self.game_running_status[room_name]:
            return
        
        room_players = self.rooms[room_name]
        ready_status = self.ready_players[room_name]
        
        # Check if we have exactly 2 players and both are ready
        if len(room_players) == 2:
            all_ready = all(ready_status.get(player, False) for player in room_players)
            if all_ready:
                print(f"🎮 AUTO-STARTING CONNECT 4 in room {room_name}! Both players are ready.")
                
                # Set game as running
                self.game_running_status[room_name] = True
                
                # Create random player assignments
                player_assignment = self.assign_random_players(room_name)
                
                # Initialize game board and turn tracking
                self.initialize_game_board(room_name)
                
                # Broadcast game start with player assignments
                self.broadcast_to_room(room_name, {
                    "Command": "Game_Started",
                    "Room_Name": room_name,
                    "Player_Assignment": player_assignment
                })
                
                # Reset ready status for next game
                for player in room_players:
                    self.ready_players[room_name][player] = False

    def create_room(self, room_name, username):
        """Create a new game room without adding the user."""
        if room_name not in self.rooms:
            self.rooms[room_name] = []
            self.ready_players[room_name] = {}
            self.game_running_status[room_name] = False
            print(f"✅ Created Connect 4 room {room_name} by player {username}")

    def join_room(self, room_name, username):
        """Add a user to an existing game room."""
        if room_name not in self.rooms:  # Allow joining non-existent rooms (server creates it)
            if len(self.rooms) >= self.max_rooms:
                print(f"🚫 Cannot create room {room_name} - maximum {self.max_rooms} rooms reached")
                return
            self.rooms[room_name] = []
            self.ready_players[room_name] = {}
            self.game_running_status[room_name] = False
        if username not in self.rooms[room_name] and len(self.rooms[room_name]) < 2:
            self.rooms[room_name].append(username)

    def send_message(self, client_socket, message):
        """Send a message to a specific client."""
        print(f"📤 Sending message: {message}")
        try:
            data = pickle.dumps(message)
            client_socket.sendall(data)
        except Exception as e:
            print(f"❌ Error sending message: {e}")

    def broadcast(self, message):
        """Broadcast a message to all connected clients."""
        for client_socket in self.clients.values():
            self.send_message(client_socket, message)

    def broadcast_to_room(self, room_name, message):
        """Broadcast a message to all users in a specific room."""
        if room_name in self.rooms:
            for username in self.rooms[room_name]:
                if username in self.clients:
                    self.send_message(self.clients[username], message)

    def broadcast_room_state(self):
        """Send the current list of available rooms to all clients."""
        response = {
            "Command": "Room_State",
            "Available_Rooms": list(self.rooms.keys()),
            "Users_In_Room": []
        }
        self.broadcast(response)

    def get_room_info(self):
        """Get formatted room information for logging."""
        if not self.rooms:
            return "No active rooms"
        
        info = []
        for room_name, players in self.rooms.items():
            ready_count = 0
            if room_name in self.ready_players:
                ready_count = sum(1 for ready in self.ready_players[room_name].values() if ready)
            game_status = "PLAYING" if self.game_running_status.get(room_name, False) else "LOBBY"
            info.append(f"{room_name}: {len(players)}/2 players ({ready_count} ready) [{game_status}]")
        return " | ".join(info)

    def shutdown(self):
        """Shutdown the server and close all connections."""
        print("🔌 Shutting down Connect 4 Game Server...")
        for client_socket in self.clients.values():
            try:
                client_socket.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        print("✅ Server shutdown complete")
        
if __name__ == "__main__":
    server = Connect4GameServer("127.0.0.1", 12345)  # Match the client's IP and port
    try:
        print("🔴 Connect 4 Game Server is running...")
        print("📋 Commands: Ctrl+C to shutdown")
        print("=" * 50)
        
        # Keep the server running and show periodic status
        import time
        while True:
            time.sleep(30)  # Show status every 30 seconds
            if server.rooms:
                print(f"📊 Current rooms: {server.get_room_info()}")
            else:
                print("📊 No active rooms")
                
    except KeyboardInterrupt:
        print("\n🛑 Shutdown signal received...")
        server.shutdown()
        sys.exit(0)