import sys
import pickle
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMainWindow, QMessageBox
from PyQt5.QtCore import Qt, QEvent, QCoreApplication
from PyQt5.QtGui import QFont

class GameMessageEvent(QEvent):
    """Custom event for passing game messages to the main thread"""
    EventType = QEvent.Type(QEvent.registerEventType())
    def __init__(self, message_type, data):
        super().__init__(self.EventType)
        self.message_type = message_type
        self.data = data

class NetworkedConnect4Game(QMainWindow):
    def __init__(self, client_socket, username, players_list, room_name, player_assignment):
        super().__init__()
        self.client_socket = client_socket
        self.username = username
        self.players_list = players_list
        self.room_name = room_name
        self.player_assignment = player_assignment
        
        # Game state
        self.board = [[0 for _ in range(7)] for _ in range(6)]
        self.current_player = 1  # 1 for Player 1 (Red), 2 for Player 2 (Yellow)
        self.game_over = False
        self.winner = None
        
        # Determine my player number and if it's my turn
        self.my_player_number = player_assignment.get(username, 1)
        self.is_my_turn = (self.my_player_number == self.current_player)
        
        print(f"Starting Connect 4 game for {username}")
        print(f"Player assignment: {player_assignment}")
        print(f"My player number: {self.my_player_number}")
        print(f"Players: {players_list}")
        
        self.init_ui()
        
        # Start receiving game messages in background
        import threading
        threading.Thread(target=self.receive_game_messages, daemon=True).start()

    def init_ui(self):
        self.setWindowTitle(f"🔴 Connect 4 - {self.room_name}")
        self.setGeometry(300, 100, 600, 700)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QWidget {
                background-color: #2b2b2b;
            }
        """)
        
        # Title
        title_label = QLabel(f"🔴 Connect 4 Game 🟡 - Room: {self.room_name}")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 20, QFont.Bold))
        title_label.setStyleSheet("color: #ffffff; margin: 20px;")
        main_layout.addWidget(title_label)
        
        # Player info
        player_info = QLabel(self.get_player_info_text())
        player_info.setAlignment(Qt.AlignCenter)
        player_info.setFont(QFont("Arial", 14))
        player_info.setStyleSheet("color: #cccccc; margin: 10px;")
        main_layout.addWidget(player_info)
        
        # Game status
        self.status_label = QLabel(self.get_turn_text())
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.status_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                background-color: #3c3f41;
                border-radius: 10px;
                padding: 15px;
                margin: 10px;
            }
        """)
        main_layout.addWidget(self.status_label)
        
        # Game board
        board_widget = QWidget()
        board_widget.setFixedSize(490, 420)
        board_widget.setStyleSheet("""
            QWidget {
                background-color: #1e4d72;
                border: 3px solid #ffffff;
                border-radius: 15px;
            }
        """)
        main_layout.addWidget(board_widget, alignment=Qt.AlignCenter)
        
        # Create board buttons
        self.board_buttons = []
        for row in range(6):
            button_row = []
            for col in range(7):
                btn = QPushButton()
                btn.setFixedSize(60, 60)
                btn.move(15 + col * 70, 15 + row * 70)
                btn.setParent(board_widget)
                btn.setEnabled(False)
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #ffffff;
                        border: 2px solid #333333;
                        border-radius: 25px;
                    }
                """)
                btn.show()
                button_row.append(btn)
            self.board_buttons.append(button_row)
        
        # Column buttons for making moves
        column_layout = QHBoxLayout()
        self.column_buttons = []
        for i in range(7):
            btn = QPushButton(f"Drop\nCol {i+1}")
            btn.setFixedSize(70, 50)
            btn.clicked.connect(lambda checked, col=i: self.make_move(col))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e90ff;
                    color: #ffffff;
                    border: none;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #4682b4;
                }
                QPushButton:pressed {
                    background-color: #1c86ee;
                }
                QPushButton:disabled {
                    background-color: #666666;
                }
            """)
            self.column_buttons.append(btn)
            column_layout.addWidget(btn)
        
        main_layout.addLayout(column_layout)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.restart_button = QPushButton("🔄 Play Again")
        self.restart_button.clicked.connect(self.request_restart)
        self.restart_button.setFixedSize(140, 40)
        self.restart_button.setEnabled(False)  # Only enabled when game ends
        self.restart_button.setStyleSheet("""
            QPushButton {
                background-color: #228B22;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #32CD32;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        control_layout.addWidget(self.restart_button)
        
        self.leave_button = QPushButton("🚪 Leave Game")
        self.leave_button.clicked.connect(self.leave_game)
        self.leave_button.setFixedSize(140, 40)
        self.leave_button.setStyleSheet("""
            QPushButton {
                background-color: #DC143C;
                color: #ffffff;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF6347;
            }
        """)
        control_layout.addWidget(self.leave_button)
        
        main_layout.addLayout(control_layout)
        
        # Instructions
        instructions = QLabel("Click column buttons to drop pieces. Get 4 in a row to win!")
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
                margin: 10px;
            }
        """)
        main_layout.addWidget(instructions)
        
        # Update button states based on turn
        self.update_button_states()

    def get_player_info_text(self):
        """Get player information text"""
        player_names = []
        for username in self.players_list:
            player_num = self.player_assignment.get(username, 1)
            color = "🔴" if player_num == 1 else "🟡"
            if username == self.username:
                player_names.append(f"Player {player_num}: {username} (You) {color}")
            else:
                player_names.append(f"Player {player_num}: {username} {color}")
        return " vs ".join(player_names)

    def get_turn_text(self):
        """Get turn information text"""
        if self.game_over:
            if self.winner:
                winner_username = self.get_username_by_player(self.winner)
                if winner_username == self.username:
                    return "🎉 You Win! 🎉"
                else:
                    return f"🎉 {winner_username} Wins! 🎉"
            else:
                return "🤝 It's a Draw! 🤝"
        else:
            current_username = self.get_username_by_player(self.current_player)
            player_color = "🔴" if self.current_player == 1 else "🟡"
            if current_username == self.username:
                return f"Your Turn {player_color}"
            else:
                return f"{current_username}'s Turn {player_color}"

    def get_username_by_player(self, player_num):
        """Get username for a player number"""
        for username, pnum in self.player_assignment.items():
            if pnum == player_num:
                return username
        return "Unknown"

    def make_move(self, column):
        """Make a move in the specified column"""
        if self.game_over:
            return
            
        if not self.is_my_turn:
            QMessageBox.information(self, "Not Your Turn", "Please wait for your turn!")
            return
            
        if column < 0 or column >= 7:
            return
            
        # Check if column is full locally first
        if self.board[0][column] != 0:
            QMessageBox.information(self, "Invalid Move", "Column is full!")
            return
        
        # Find the lowest available row in the column
        row = -1
        for r in range(5, -1, -1):
            if self.board[r][column] == 0:
                row = r
                break
                
        if row == -1:
            QMessageBox.information(self, "Invalid Move", "Column is full!")
            return
        
        # Make the move locally FIRST
        self.board[row][column] = self.my_player_number
        
        # Update turn locally FIRST (switch to other player)
        self.current_player = 2 if self.current_player == 1 else 1
        self.is_my_turn = (self.my_player_number == self.current_player)
        
        # Update UI immediately
        self.update_board_display()
        self.status_label.setText(self.get_turn_text())
        self.update_button_states()
        
        # Check for win or draw
        game_over = False
        winner = None
        is_draw = False
        
        if self.check_winner(row, column, self.my_player_number):
            game_over = True
            winner = self.my_player_number
            self.game_over = True
            self.winner = self.my_player_number
            self.restart_button.setEnabled(True)
            self.update_button_states()
            QMessageBox.information(self, "Congratulations!", "🎉 You win! 🎉")
        elif self.is_board_full():
            game_over = True
            is_draw = True
            self.game_over = True
            self.restart_button.setEnabled(True)
            self.update_button_states()
            QMessageBox.information(self, "Game Over", "🤝 It's a draw! 🤝")
        
        # Send move, turn, and board state to server
        self.send_game_message({
            "Command": "game_move",
            "room_name": self.room_name,
            "username": self.username,
            "col": column,
            "row": row,  # Include the row where piece was placed
            "player": self.my_player_number,
            "board_array": self.board,  # Send current board state
            "current_player": self.current_player,  # Send updated turn
            "game_over": game_over,
            "winner": winner,
            "is_draw": is_draw
        })

    def apply_move(self, column, player):
        """Apply a move received from server"""
        # Find the lowest available row in the column
        row = -1
        for r in range(5, -1, -1):
            if self.board[r][column] == 0:
                row = r
                break
                
        if row == -1:
            print(f"Error: Column {column} is full!")
            return False
            
        # Make the move
        self.board[row][column] = player
        self.update_board_display()
        
        # Check for win
        if self.check_winner(row, column, player):
            self.game_over = True
            self.winner = player
            self.restart_button.setEnabled(True)
            self.update_button_states()
            
            winner_username = self.get_username_by_player(player)
            if winner_username == self.username:
                QMessageBox.information(self, "Congratulations!", "🎉 You win! 🎉")
            else:
                QMessageBox.information(self, "Game Over", f"🎉 {winner_username} wins! 🎉")
            return True
        
        # Check for draw
        if self.is_board_full():
            self.game_over = True
            self.restart_button.setEnabled(True)
            self.update_button_states()
            QMessageBox.information(self, "Game Over", "🤝 It's a draw! 🤝")
            return True
        
        return False

    def update_turn(self, new_current_player):
        """Update whose turn it is"""
        self.current_player = new_current_player
        self.is_my_turn = (self.my_player_number == self.current_player)
        self.status_label.setText(self.get_turn_text())
        self.update_button_states()

    def update_button_states(self):
        """Enable/disable column buttons based on game state and turn"""
        enable_buttons = not self.game_over and self.is_my_turn
        for btn in self.column_buttons:
            btn.setEnabled(enable_buttons)

    def update_board_display(self):
        """Update the visual representation of the game board"""
        for row in range(6):
            for col in range(7):
                btn = self.board_buttons[row][col]
                cell_value = self.board[row][col]
                if cell_value == 0:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #ffffff;
                            border: 2px solid #333333;
                            border-radius: 25px;
                        }
                    """)
                elif cell_value == 1:
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #ff4444;
                            border: 2px solid #333333;
                            border-radius: 25px;
                        }
                    """)
                else:  # cell_value == 2
                    btn.setStyleSheet("""
                        QPushButton {
                            background-color: #ffff44;
                            border: 2px solid #333333;
                            border-radius: 25px;
                        }
                    """)

    def check_winner(self, row, col, player):
        """Check if the last move resulted in a win"""
        directions = [
            (0, 1),   # Horizontal
            (1, 0),   # Vertical
            (1, 1),   # Diagonal /
            (1, -1)   # Diagonal \
        ]
        
        for dr, dc in directions:
            count = 1  # Count the piece just placed
            
            # Check in positive direction
            r, c = row + dr, col + dc
            while 0 <= r < 6 and 0 <= c < 7 and self.board[r][c] == player:
                count += 1
                r, c = r + dr, c + dc
                
            # Check in negative direction
            r, c = row - dr, col - dc
            while 0 <= r < 6 and 0 <= c < 7 and self.board[r][c] == player:
                count += 1
                r, c = r - dr, c - dc
                
            if count >= 4:
                return True
        
        return False

    def handle_board_update(self, message):
        """Handle board update from other player"""
        board_array = message.get("board_array")
        current_player = message.get("current_player")
        game_over = message.get("game_over", False)
        winner = message.get("winner", None)
        is_draw = message.get("is_draw", False)
        other_username = message.get("username")
        col = message.get("col")
        row = message.get("row")
        player = message.get("player")
        
        # Validate the move before applying
        if board_array:
            # Check if the move is valid by comparing with our current board
            temp_board = [row[:] for row in self.board]  # Copy current board
            
            # Apply the move to temp board
            if row is not None and col is not None and player is not None:
                if (0 <= row < 6 and 0 <= col < 7 and 
                    temp_board[row][col] == 0):  # Check if spot was empty
                    
                    temp_board[row][col] = player
                    
                    # Only update if the received board matches our expected result
                    boards_match = True
                    for r in range(6):
                        for c in range(7):
                            if board_array[r][c] != temp_board[r][c]:
                                boards_match = False
                                break
                        if not boards_match:
                            break
                    
                    if boards_match:
                        # Update local board with received state
                        self.board = [row[:] for row in board_array]  # Deep copy
                        
                        # Update turn if provided
                        if current_player is not None:
                            self.current_player = current_player
                            self.is_my_turn = (self.my_player_number == self.current_player)
                        
                        # Update UI
                        self.update_board_display()
                        self.status_label.setText(self.get_turn_text())
                        self.update_button_states()
                        
                        # Handle game end
                        if game_over:
                            self.game_over = True
                            self.restart_button.setEnabled(True)
                            self.update_button_states()
                            
                            if winner:
                                self.winner = winner
                                if winner == self.my_player_number:
                                    QMessageBox.information(self, "Congratulations!", "🎉 You win! 🎉")
                                else:
                                    QMessageBox.information(self, "Game Over", f"🎉 {other_username} wins! 🎉")
                            elif is_draw:
                                QMessageBox.information(self, "Game Over", "🤝 It's a draw! 🤝")
                    else:
                        print(f"⚠️ Board sync error - received board doesn't match expected state")
                        # Request board sync from server if needed
                        self.send_game_message({
                            "Command": "request_board_sync",
                            "room_name": self.room_name,
                            "username": self.username
                        })
                else:
                    print(f"⚠️ Invalid move received: row={row}, col={col}, player={player}")
            else:
                print("⚠️ Incomplete move data received")
        else:
            print("⚠️ No board data received")
    
    def is_board_full(self):
        """Check if the board is full"""
        for col in range(7):
            if self.board[0][col] == 0:
                return False
        return True

    def reset_game(self):
        """Reset the game to initial state"""
        self.board = [[0 for _ in range(7)] for _ in range(6)]
        self.current_player = 1
        self.game_over = False
        self.winner = None
        self.is_my_turn = (self.my_player_number == 1)
        
        # Update UI
        self.status_label.setText(self.get_turn_text())
        self.restart_button.setEnabled(False)
        self.update_board_display()
        self.update_button_states()

    def request_restart(self):
        """Request a game restart"""
        self.send_game_message({
            "Command": "game_reset",
            "room_name": self.room_name,
            "username": self.username
        })

    def leave_game(self):
        """Leave the game and return to lobby"""
        self.send_game_message({
            "Command": "player_left_game",
            "room_name": self.room_name,
            "username": self.username
        })
        self.close()

    def send_game_message(self, message):
        """Send a message to the server"""
        try:
            data = pickle.dumps(message)
            self.client_socket.sendall(data)
        except Exception as e:
            print(f"Error sending game message: {e}")
            QMessageBox.critical(self, "Connection Error", f"Lost connection to server: {e}")
            self.close()

    def receive_game_messages(self):
        """Receive game messages from server"""
        while True:
            try:
                data = self.client_socket.recv(1048576)
                if not data:
                    break
                message = pickle.loads(data)
                if message:
                    QCoreApplication.postEvent(self, GameMessageEvent("game_message", message))
            except Exception as e:
                print(f"Error receiving game message: {e}")
                break

    def customEvent(self, event):
        """Handle custom events from the networking thread"""
        if event.type() == GameMessageEvent.EventType:
            if event.message_type == "game_message":
                self.process_game_message(event.data)

    def process_game_message(self, message):
        """Process game messages from server"""
        try:
            command = message.get("Command", "")
            
            if command == "board_update" and message.get("room_name") == self.room_name:
                # Handle board update from other player
                self.handle_board_update(message)
                
            elif command == "turn_update" and message.get("room_name") == self.room_name:
                # Update whose turn it is
                new_current_player = message.get("current_player")
                if new_current_player:
                    print(f"Turn update: Now Player {new_current_player}'s turn")
                    self.update_turn(new_current_player)
                
            elif command == "game_reset" and message.get("room_name") == self.room_name:
                # Reset the game
                username = message.get("username")
                print(f"Game reset by {username}")
                self.reset_game()
                QMessageBox.information(self, "Game Reset", f"Game reset by {username}")
                
            elif command == "game_won" and message.get("room_name") == self.room_name:
                # Handle game won
                winner_player = message.get("winner")
                winner_username = message.get("winner_username")
                if winner_player:
                    self.game_over = True
                    self.winner = winner_player
                    self.restart_button.setEnabled(True)
                    self.update_button_states()
                    self.status_label.setText(self.get_turn_text())
                
            elif command == "game_draw" and message.get("room_name") == self.room_name:
                # Handle game draw
                self.game_over = True
                self.winner = None
                self.restart_button.setEnabled(True)
                self.update_button_states()
                self.status_label.setText(self.get_turn_text())
                
            elif command == "game_ended_player_left" and message.get("room_name") == self.room_name:
                # Handle player leaving mid-game
                left_player = message.get("left_player", "")
                winner = message.get("winner", "")
                
                if winner == self.username:
                    QMessageBox.information(self, "You Win!", f"🎉 You win! {left_player} left the game.")
                else:
                    QMessageBox.information(self, "Player Left", f"🚪 {left_player} left the game.")
                
                self.close()  # Return to lobby
                
        except Exception as e:
            print(f"Error processing game message: {e}")

    def closeEvent(self, event):
        """Handle window close event"""
        # Only send leave message if game is still active
        if not self.game_over:
            try:
                self.send_game_message({
                    "Command": "player_left_game",
                    "room_name": self.room_name,
                    "username": self.username
                })
            except:
                pass
        event.accept()

def main(client_socket, username, players_list, room_name, player_assignment):
    """Main function to start the networked Connect 4 game"""
    # Create and show the game window
    game = NetworkedConnect4Game(client_socket, username, players_list, room_name, player_assignment)
    game.show()
    
    # Return the game instance so it stays alive
    return game

if __name__ == "__main__":
    # This won't be called in the networked version, but kept for compatibility
    print("This is the networked version of Connect 4. Please run through the client.")