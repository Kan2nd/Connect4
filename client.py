import sys
import pickle
import threading
import socket
import errno
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QTextEdit, QPushButton, QLineEdit, QLabel, QMainWindow, QHBoxLayout, QMessageBox, QGridLayout, QFrame
from PyQt5.QtCore import Qt, QEvent, QCoreApplication
import time

class MessageEvent(QEvent):
    # Custom event for passing messages to the main thread
    EventType = QEvent.Type(QEvent.registerEventType())
    def __init__(self, message_type, data):
        super().__init__(self.EventType)
        self.message_type = message_type  # 'chat', 'rooms', 'status', or 'file'
        self.data = data

class GameLobby(QMainWindow):  
    def __init__(self, current_user, room_name, list_of_users, client_socket):
        super().__init__()  
        self.current_user = current_user 
        self.room_name = room_name
        self.list_of_users_in_room = [user for user in (list_of_users or []) if isinstance(user, str)]
        self.client_socket = client_socket
        self.ready_players = set()  # Track ready players
        self.is_ready = False
        print(f"Initializing GameLobby for user {self.current_user} in room {self.room_name} with users {self.list_of_users_in_room}")
        self.init_ui()
        self.show()

    def init_ui(self):
        self.setWindowTitle(f"🔴 CONNECT 4 - {self.room_name}")
        self.setGeometry(400, 150, 1000, 750)

        # Main styling - Dark theme for Connect 4
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #1a1a2e, stop:0.3 #16213e, stop:0.7 #0f3460, stop:1 #0c2d48);
            }
            QWidget {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header with room name and game title
        header_widget = self.create_header()
        main_layout.addWidget(header_widget)

        # Main game area
        game_area = QHBoxLayout()
        game_area.setSpacing(25)

        # Left panel - Players (fixed height to prevent movement)
        players_panel = self.create_players_panel()
        game_area.addWidget(players_panel, stretch=1)

        # Right panel - Chat and controls
        right_panel = self.create_right_panel()
        game_area.addWidget(right_panel, stretch=2)

        main_layout.addLayout(game_area)

        # Bottom control bar
        controls = self.create_control_bar()
        main_layout.addWidget(controls)

    def create_header(self):
        header_frame = QFrame()
        header_frame.setFixedHeight(100)
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #dc143c, stop:0.3 #ff4500, stop:0.5 #ffd700, 
                    stop:0.7 #ff4500, stop:1 #dc143c);
                border-radius: 20px;
                border: 3px solid #2c3e50;
            }
        """)
        
        header_layout = QVBoxLayout(header_frame)
        header_layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("🔴 CONNECT 4 LOBBY")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: bold;
                color: #ffffff;
                text-shadow: 3px 3px 6px rgba(0,0,0,0.8);
                margin: 5px;
            }
        """)
        header_layout.addWidget(title)
        
        room_info = QLabel(f"Room: {self.room_name}")
        room_info.setAlignment(Qt.AlignCenter)
        room_info.setStyleSheet("""
            QLabel {
                font-size: 18px;
                color: #ecf0f1;
                font-weight: bold;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.6);
            }
        """)
        header_layout.addWidget(room_info)
        
        return header_frame

    def create_players_panel(self):
        panel_frame = QFrame()
        panel_frame.setFixedHeight(400)  # Fixed height to prevent movement
        panel_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2c3e50, stop:0.5 #34495e, stop:1 #2c3e50);
                border-radius: 20px;
                border: 3px solid #95a5a6;
            }
        """)
        
        layout = QVBoxLayout(panel_frame)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("👥 PLAYERS (Max 2)")
        title.setAlignment(Qt.AlignCenter)
        title.setFixedHeight(50)  # Fixed height
        title.setStyleSheet("""
            QLabel {
                font-size: 22px;
                font-weight: bold;
                color: #ecf0f1;
                background: rgba(52, 73, 94, 0.8);
                border-radius: 12px;
                padding: 12px;
                border: 2px solid #7f8c8d;
            }
        """)
        layout.addWidget(title)
        
        # Players container with fixed height
        players_container = QFrame()
        players_container.setFixedHeight(200)  # Fixed height
        players_container.setStyleSheet("""
            QFrame {
                background: rgba(0,0,0,0.4);
                border-radius: 15px;
                border: 2px solid #7f8c8d;
            }
        """)
        
        self.players_layout = QVBoxLayout(players_container)
        self.players_layout.setSpacing(8)
        self.players_layout.setContentsMargins(15, 15, 15, 15)
        
        layout.addWidget(players_container)
        
        # Ready status summary with fixed height
        self.ready_summary = QLabel("⏳ Waiting for players...")
        self.ready_summary.setAlignment(Qt.AlignCenter)
        self.ready_summary.setFixedHeight(60)  # Fixed height
        self.ready_summary.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #f39c12;
                background: rgba(0,0,0,0.6);
                border-radius: 10px;
                padding: 10px;
                border: 2px solid #f39c12;
            }
        """)
        layout.addWidget(self.ready_summary)
        
        # Add stretch to fill remaining space
        layout.addStretch()
        
        self.update_players_display()
        return panel_frame

    def create_right_panel(self):
        right_frame = QFrame()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setSpacing(20)
        
        # Chat section
        chat_frame = QFrame()
        chat_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #34495e, stop:0.5 #2c3e50, stop:1 #34495e);
                border-radius: 20px;
                border: 3px solid #95a5a6;
            }
        """)
        
        chat_layout = QVBoxLayout(chat_frame)
        chat_layout.setContentsMargins(20, 20, 20, 20)
        chat_layout.setSpacing(15)
        
        # Chat title
        chat_title = QLabel("💬 GAME CHAT")
        chat_title.setAlignment(Qt.AlignCenter)
        chat_title.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: bold;
                color: #ecf0f1;
                background: rgba(52, 73, 94, 0.8);
                border-radius: 12px;
                padding: 12px;
                border: 2px solid #7f8c8d;
            }
        """)
        chat_layout.addWidget(chat_title)
        
        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setMinimumHeight(300)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background: rgba(0,0,0,0.7);
                color: #ecf0f1;
                border: 2px solid #7f8c8d;
                border-radius: 15px;
                padding: 15px;
                font-size: 14px;
                line-height: 1.5;
            }
            QScrollBar:vertical {
                background: rgba(0,0,0,0.3);
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #3498db;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5dade2;
            }
        """)
        chat_layout.addWidget(self.chat_display)
        
        # Message input
        input_container = QHBoxLayout()
        input_container.setSpacing(10)
        
        self.message_input = QLineEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.8);
                color: #ecf0f1;
                border: 2px solid #7f8c8d;
                border-radius: 12px;
                padding: 15px;
                font-size: 15px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
                background: rgba(0,0,0,0.9);
            }
        """)
        self.message_input.returnPressed.connect(self.send_message)
        input_container.addWidget(self.message_input)
        
        send_btn = QPushButton("📤")
        send_btn.setFixedSize(50, 50)
        send_btn.clicked.connect(self.send_message)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #27ae60, stop:1 #2ecc71);
                border: 2px solid #229954;
                border-radius: 25px;
                font-size: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #58d68d, stop:1 #7dcea0);
                transform: scale(1.05);
            }
            QPushButton:pressed {
                background: #229954;
            }
        """)
        input_container.addWidget(send_btn)
        
        chat_layout.addLayout(input_container)
        right_layout.addWidget(chat_frame)
        
        return right_frame

    def create_control_bar(self):
        control_frame = QFrame()
        control_frame.setFixedHeight(100)
        control_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #8e44ad, stop:0.5 #9b59b6, stop:1 #8e44ad);
                border-radius: 20px;
                border: 3px solid #7d3c98;
            }
        """)
        
        control_layout = QHBoxLayout(control_frame)
        control_layout.setSpacing(20)
        control_layout.setContentsMargins(20, 20, 20, 20)
        
        # Ready button
        self.ready_button = QPushButton("⚡ READY TO PLAY!")
        self.ready_button.setFixedHeight(60)
        self.ready_button.clicked.connect(self.toggle_ready)
        self.ready_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
                border: 3px solid #a93226;
                border-radius: 15px;
                padding: 0px 40px;
                font-size: 20px;
                font-weight: bold;
                min-width: 200px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #ec7063, stop:1 #cb4335);
                transform: scale(1.02);
            }
        """)
        control_layout.addWidget(self.ready_button)
        
        # Spacer
        control_layout.addStretch()
        
        # Leave button
        leave_btn = QPushButton("🚪 Leave")
        leave_btn.setFixedHeight(60)
        leave_btn.clicked.connect(self.close)
        leave_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #95a5a6, stop:1 #7f8c8d);
                color: white;
                border: 3px solid #566573;
                border-radius: 15px;
                padding: 0px 30px;
                font-size: 16px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #b2bec3, stop:1 #95a5a6);
                transform: scale(1.02);
            }
        """)
        control_layout.addWidget(leave_btn)
        
        return control_frame

    def create_player_card(self, username, is_ready):
        card = QFrame()
        card.setFixedHeight(60)
        
        # Determine player number and color
        player_num = self.list_of_users_in_room.index(username) + 1 if username in self.list_of_users_in_room else 1
        
        if is_ready:
            if player_num == 1:
                # Player 1 - Red
                card.setStyleSheet("""
                    QFrame {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0 #dc143c, stop:1 #b91c1c);
                        border: 2px solid #991b1b;
                        border-radius: 12px;
                    }
                """)
            else:
                # Player 2 - Gold
                card.setStyleSheet("""
                    QFrame {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0 #ffd700, stop:1 #f59e0b);
                        border: 2px solid #d97706;
                        border-radius: 12px;
                    }
                """)
        else:
            card.setStyleSheet("""
                QFrame {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #6b7280, stop:1 #4b5563);
                    border: 2px solid #374151;
                    border-radius: 12px;
                }
            """)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(15, 10, 15, 10)
        
        # Player number and piece indicator
        if player_num == 1:
            piece_icon = QLabel("🔴")
        else:
            piece_icon = QLabel("🟡")
        piece_icon.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
            }
        """)
        layout.addWidget(piece_icon)
        
        # Status icon
        status_icon = QLabel("✅" if is_ready else "⏳")
        status_icon.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
            }
        """)
        layout.addWidget(status_icon)
        
        # Username
        name_label = QLabel(f"Player {player_num}: {username}")
        if username == self.current_user:
            name_label.setText(f"Player {player_num}: {username} (You)")
        name_label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: white;
            }
        """)
        layout.addWidget(name_label)
        
        layout.addStretch()
        
        return card

    def update_players_display(self):
        # Clear existing player cards
        for i in reversed(range(self.players_layout.count())):
            child = self.players_layout.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        # Add player cards
        for username in self.list_of_users_in_room:
            is_ready = username in self.ready_players
            card = self.create_player_card(username, is_ready)
            self.players_layout.addWidget(card)
        
        # Add spacer to maintain consistent layout
        self.players_layout.addStretch()
        
        # Update ready summary
        ready_count = len(self.ready_players)
        total_count = len(self.list_of_users_in_room)
        time.sleep(0.5)  # Simulate processing delay for UI update
        if ready_count == total_count and total_count == 2:
            self.ready_summary.setText("🎮 Both players ready! Starting Connect 4...")
            self.ready_summary.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #27ae60;
                    background: rgba(39, 174, 96, 0.2);
                    border-radius: 10px;
                    padding: 10px;
                    border: 2px solid #27ae60;
                }
            """)
            print("AUTO START CONNECT 4 GAME")
            self.chat_display.append("🎮 <b style='color: #27ae60;'>CONNECT 4 STARTING AUTOMATICALLY!</b>")
            
            # Auto-start the game when both players are ready
            send_start_game = {
                "Command": "Auto_Start_Game",
                "Room_Name": self.room_name,
                "User_Name": self.current_user
            }
            try:
                data = pickle.dumps(send_start_game)
                client_menu.client_socket.sendall(data)
            except Exception as e:
                self.chat_display.append(f"<span style='color: #e74c3c;'>❌ Error auto-starting game: {e}</span>")
        elif total_count < 2:
            self.ready_summary.setText(f"⏳ Need 2 players ({total_count}/2)")
            self.ready_summary.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #e74c3c;
                    background: rgba(231, 76, 60, 0.2);
                    border-radius: 10px;
                    padding: 10px;
                    border: 2px solid #e74c3c;
                }
            """)
        else:
            self.ready_summary.setText(f"⏳ Ready: {ready_count}/2")
            self.ready_summary.setStyleSheet("""
                QLabel {
                    font-size: 16px;
                    font-weight: bold;
                    color: #f39c12;
                    background: rgba(243, 156, 18, 0.2);
                    border-radius: 10px;
                    padding: 10px;
                    border: 2px solid #f39c12;
                }
            """)

    def toggle_ready(self):
        self.is_ready = not self.is_ready
        ready_message = "READY" if self.is_ready else "NOT_READY"
        
        # Update button appearance
        if self.is_ready:
            self.ready_button.setText("✅ READY!")
            self.ready_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #27ae60, stop:1 #229954);
                    color: white;
                    border: 3px solid #1e8449;
                    border-radius: 15px;
                    padding: 0px 40px;
                    font-size: 20px;
                    font-weight: bold;
                    min-width: 200px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #58d68d, stop:1 #52c4a5);
                    transform: scale(1.02);
                }
            """)
        else:
            self.ready_button.setText("⚡ READY TO PLAY!")
            self.ready_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #e74c3c, stop:1 #c0392b);
                    color: white;
                    border: 3px solid #a93226;
                    border-radius: 15px;
                    padding: 0px 40px;
                    font-size: 20px;
                    font-weight: bold;
                    min-width: 200px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #ec7063, stop:1 #cb4335);
                    transform: scale(1.02);
                }
            """)

        # Send ready status to server
        message = {
            "Command": "Player_Ready",
            "Room_Name": self.room_name,
            "User_Name": self.current_user,
            "Ready_Status": ready_message
        }
        try:
            data = pickle.dumps(message)
            client_menu.client_socket.sendall(data)
        except Exception as e:
            self.chat_display.append(f"<span style='color: #e74c3c;'>❌ Error sending ready status: {e}</span>")

    def handle_ready_status(self, username, ready_status):
        if ready_status == "READY":
            self.ready_players.add(username)
        else:
            self.ready_players.discard(username)
        self.update_players_display()

    def handle_game_state_update(self, message):
        """Handle game state changes from server"""
        game_running = message.get("Game_Running", False)
        if not game_running:  # Game ended
            # Reset all ready states
            self.ready_players.clear()
            self.is_ready = False
            # Reset ready button appearance
            self.ready_button.setText("⚡ READY TO PLAY!")
            self.ready_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #e74c3c, stop:1 #c0392b);
                    color: white;
                    border: 3px solid #a93226;
                    border-radius: 15px;
                    padding: 0px 40px;
                    font-size: 20px;
                    font-weight: bold;
                    min-width: 200px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                        stop:0 #ec7063, stop:1 #cb4335);
                    transform: scale(1.02);
                }
            """)
            # Update players display
            self.update_players_display()
            # Show game ended message
            self.chat_display.append("<span style='color: #f39c12;'>🎮 Game ended! All players reset to NOT READY.</span>")
            
    def send_message(self):
        message_text = self.message_input.text().strip()
        if message_text and client_menu.client_socket:
            message = {
                "Command": "Sending_Message",
                "Room_Name": self.room_name,
                "User_Name": self.current_user,
                "Text": message_text
            }
            try:
                data = pickle.dumps(message)
                client_menu.client_socket.sendall(data)
                self.message_input.clear()
            except Exception as e:
                self.chat_display.append(f"<span style='color: #e74c3c;'>❌ Error sending message: {e}</span>")
        else:
            self.chat_display.append("<span style='color: #f39c12;'>⚠️ Please enter a message to send.</span>")

    def updating_text_edit(self, message, list_of_users):
        self.list_of_users_in_room = [user for user in (list_of_users or []) if isinstance(user, str)]
        self.chat_display.append(f"<span style='color: #ecf0f1;'>💬 {message}</span>")
        self.update_players_display()

    def closeEvent(self, event):
        if self.client_socket:
            try:
                leave_message = {
                    "Command": "Sending_Message",
                    "Room_Name": self.room_name,
                    "User_Name": self.current_user,
                    "Text": f"{self.current_user} has left the room."
                }
                data = pickle.dumps(leave_message)
                self.client_socket.sendall(data)
                client_menu.alreadyinroom = False
            except:
                pass
        event.accept()
#
#
#
#
#
#
#
class GameMainMenu(QMainWindow):
    def __init__(self, host, port):
        super().__init__()
        self.game_running = False  # Track if the game is running
        self.host = host
        self.port = port
        self.list_of_users_in_room = None
        self.username = None  
        self.room_name = None
        self.list_of_available_rooms = []
        self.client_socket = None
        self.chatroom = None
        self.running = True
        self.is_disconnected = False
        self.alreadyinroom = False
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("🔴 CONNECT 4")
        self.setGeometry(500, 200, 700, 600)
        
        # Main styling - Dark theme for Connect 4
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #0c0c0c, stop:0.3 #1a1a2e, stop:0.7 #16213e, stop:1 #0f3460);
            }
            QWidget {
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(25)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Title section
        title_section = self.create_title_section()
        main_layout.addWidget(title_section)

        # Connection section
        connection_section = self.create_connection_section()
        main_layout.addWidget(connection_section)

        # Rooms section
        rooms_section = self.create_rooms_section()
        main_layout.addWidget(rooms_section)

        main_layout.addStretch()

    def create_title_section(self):
        title_frame = QFrame()
        title_frame.setFixedHeight(120)
        title_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #dc143c, stop:0.15 #ff4500, stop:0.3 #ffd700, 
                    stop:0.45 #ff4500, stop:0.6 #dc143c, stop:0.75 #b91c1c, 
                    stop:0.9 #dc143c, stop:1 #ff4500);
                border-radius: 25px;
                border: 4px solid #2c3e50;
            }
        """)
        
        layout = QVBoxLayout(title_frame)
        layout.setAlignment(Qt.AlignCenter)
        
        title = QLabel("🔴 CONNECT 4")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                font-size: 42px;
                font-weight: bold;
                color: #ffffff;
                text-shadow: 4px 4px 8px rgba(0,0,0,0.9);
                margin: 10px;
            }
        """)
        layout.addWidget(title)
        
        subtitle = QLabel("Connect Four in a Row to Win!")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #ecf0f1;
                font-style: italic;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.7);
            }
        """)
        layout.addWidget(subtitle)
        
        return title_frame

    def create_connection_section(self):
        conn_frame = QFrame()
        conn_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2c3e50, stop:0.5 #34495e, stop:1 #2c3e50);
                border-radius: 20px;
                border: 3px solid #95a5a6;
            }
        """)
        
        layout = QVBoxLayout(conn_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)
        
        # Section title
        conn_title = QLabel("🚀 JOIN THE GAME")
        conn_title.setAlignment(Qt.AlignCenter)
        conn_title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ecf0f1;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(conn_title)
        
        # Server info
        server_info = QLabel(f"🌐 Server: {self.host}:{self.port}")
        server_info.setAlignment(Qt.AlignCenter)
        server_info.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #bdc3c7;
                margin-bottom: 15px;
            }
        """)
        layout.addWidget(server_info)
        
        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("🎮 Enter your player name")
        self.username_input.setFixedHeight(50)
        self.username_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.7);
                color: #ffffff;
                border: 3px solid #7f8c8d;
                border-radius: 15px;
                padding: 0px 20px;
                font-size: 18px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 3px solid #3498db;
                background: rgba(0,0,0,0.9);
            }
        """)
        layout.addWidget(self.username_input)
        
        # Connection buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        self.connect_button = QPushButton("🚀 CONNECT")
        self.connect_button.setFixedHeight(55)
        self.connect_button.clicked.connect(self.Create_socket)
        self.connect_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #27ae60, stop:1 #229954);
                color: white;
                border: 3px solid #1e8449;
                border-radius: 15px;
                padding: 0px 40px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #58d68d, stop:1 #52c4a5);
                transform: scale(1.02);
            }
            QPushButton:disabled {
                background: #566573;
                border: 3px solid #34495e;
            }
        """)
        button_layout.addWidget(self.connect_button)
        
        self.disconnect_button = QPushButton("🔌 DISCONNECT")
        self.disconnect_button.setFixedHeight(55)
        self.disconnect_button.clicked.connect(self.disconnect)
        self.disconnect_button.setEnabled(False)
        self.disconnect_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #e74c3c, stop:1 #c0392b);
                color: white;
                border: 3px solid #a93226;
                border-radius: 15px;
                padding: 0px 40px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #ec7063, stop:1 #cb4335);
                transform: scale(1.02);
            }
            QPushButton:disabled {
                background: #566573;
                border: 3px solid #34495e;
            }
        """)
        button_layout.addWidget(self.disconnect_button)
        
        layout.addLayout(button_layout)
        return conn_frame

    def create_rooms_section(self):
        rooms_frame = QFrame()
        rooms_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #8e44ad, stop:0.5 #9b59b6, stop:1 #8e44ad);
                border-radius: 20px;
                border: 3px solid #7d3c98;
            }
        """)
        
        layout = QVBoxLayout(rooms_frame)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 25, 30, 25)
        
        # Section title
        rooms_title = QLabel("🏠 GAME ROOMS")
        rooms_title.setAlignment(Qt.AlignCenter)
        rooms_title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #ffffff;
                margin-bottom: 10px;
            }
        """)
        layout.addWidget(rooms_title)
        
        # Available rooms display
        rooms_container = QFrame()
        rooms_container.setFixedHeight(120)
        rooms_container.setStyleSheet("""
            QFrame {
                background: rgba(0,0,0,0.4);
                border: 3px solid #6c3483;
                border-radius: 15px;
            }
        """)
        
        rooms_container_layout = QVBoxLayout(rooms_container)
        rooms_container_layout.setContentsMargins(15, 10, 15, 10)
        
        rooms_label = QLabel("Available Rooms:")
        rooms_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #ecf0f1;
                font-weight: bold;
            }
        """)
        rooms_container_layout.addWidget(rooms_label)
        
        self.rooms_grid = QGridLayout()
        self.rooms_grid.setSpacing(8)
        rooms_container_layout.addLayout(self.rooms_grid)
        
        layout.addWidget(rooms_container)
        
        # Room input
        self.room_input = QLineEdit()
        self.room_input.setPlaceholderText("🔴 Enter room name")
        self.room_input.setFixedHeight(50)
        self.room_input.setStyleSheet("""
            QLineEdit {
                background: rgba(0,0,0,0.7);
                color: #ffffff;
                border: 3px solid #6c3483;
                border-radius: 15px;
                padding: 0px 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 3px solid #f39c12;
                background: rgba(0,0,0,0.9);
            }
        """)
        layout.addWidget(self.room_input)
        
        # Room action buttons
        room_buttons_layout = QHBoxLayout()
        room_buttons_layout.setSpacing(15)
        
        self.create_room_button = QPushButton("🏗️ CREATE ROOM")
        self.create_room_button.setFixedHeight(55)
        self.create_room_button.clicked.connect(self.Create_room)
        self.create_room_button.setEnabled(False)
        self.create_room_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #f39c12, stop:1 #e67e22);
                color: white;
                border: 3px solid #d68910;
                border-radius: 15px;
                padding: 0px 30px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #f7dc6f, stop:1 #f4d03f);
                transform: scale(1.02);
            }
            QPushButton:disabled {
                background: #566573;
                border: 3px solid #34495e;
            }
        """)
        room_buttons_layout.addWidget(self.create_room_button)
        
        self.join_room_button = QPushButton("🚪 JOIN ROOM")
        self.join_room_button.setFixedHeight(55)
        self.join_room_button.clicked.connect(self.Join_room)
        self.join_room_button.setEnabled(False)
        self.join_room_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #27ae60, stop:1 #229954);
                color: white;
                border: 3px solid #1e8449;
                border-radius: 15px;
                padding: 0px 30px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #58d68d, stop:1 #52c4a5);
                transform: scale(1.02);
            }
            QPushButton:disabled {
                background: #566573;
                border: 3px solid #34495e;
            }
        """)
        room_buttons_layout.addWidget(self.join_room_button)
        
        layout.addLayout(room_buttons_layout)
        
        return rooms_frame

    def update_rooms_display(self):
        # Clear existing room buttons
        for i in reversed(range(self.rooms_grid.count())):
            child = self.rooms_grid.itemAt(i).widget()
            if child:
                child.deleteLater()
        
        # Add room buttons in a 2x2 grid
        if not self.list_of_available_rooms:
            no_rooms_label = QLabel("No active rooms")
            no_rooms_label.setAlignment(Qt.AlignCenter)
            no_rooms_label.setStyleSheet("""
                QLabel {
                    color: #bdc3c7;
                    font-style: italic;
                    font-size: 14px;
                }
            """)
            self.rooms_grid.addWidget(no_rooms_label, 0, 0, 1, 2)
        else:
            for i, room in enumerate(self.list_of_available_rooms[:4]):  # Max 4 rooms
                row = i // 2
                col = i % 2
                
                room_btn = QPushButton(f"🔴 {room}")
                room_btn.setFixedHeight(30)
                room_btn.clicked.connect(lambda checked, r=room: self.select_room(r))
                room_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0 #2980b9, stop:1 #3498db);
                        color: white;
                        border: 2px solid #21618c;
                        border-radius: 8px;
                        font-size: 12px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                            stop:0 #5dade2, stop:1 #85c1e9);
                        transform: scale(1.05);
                    }
                """)
                self.rooms_grid.addWidget(room_btn, row, col)

    def select_room(self, room_name):
        self.room_input.setText(room_name)

    def Create_socket(self):
        check = self.username_input.text().strip()
        if not check:
            self.username_input.setPlaceholderText("🔴Please enter a username to connect.")
            return
        
        self.username = self.username_input.text().strip()
        if self.client_socket:
            #Try to close existing socket if it exists
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        try:
            #this is a tcp socket which will connect to the server
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            # Set disable the connect button and enable the disconnect button
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(True)
            self.username_input.setEnabled(False)
            self.running = True
            self.is_disconnected = False
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Error connecting to server: {e}")
            self.client_socket = None
            return
            
        self.send_message({
            "Command": "Check_Username",
            "User_Name": self.username
        })
        
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def disconnect(self):
        if self.is_disconnected:
            return
        self.running = False
        self.is_disconnected = True
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(False)
        self.username_input.setEnabled(True)
        self.create_room_button.setEnabled(False)
        self.join_room_button.setEnabled(False)
        self.list_of_available_rooms = []
        self.update_rooms_display()
        if self.chatroom:
            self.chatroom.close()
            self.chatroom = None

    def receive_messages(self):
        while self.running and self.client_socket:
            try:
                data = self.client_socket.recv(1048576)
                if not data:
                    QCoreApplication.postEvent(self, MessageEvent("status", "Server disconnected."))
                    self.disconnect()
                    break
                message = pickle.loads(data)
                if message:
                    if message["Command"] in ["Join_Room", "Sending_Message", "Player_Ready","Game_State_Update"]:
                        QCoreApplication.postEvent(self, MessageEvent("chat", message))
                    elif message["Command"] in ["Room_State", "Check_Username"]:
                        QCoreApplication.postEvent(self, MessageEvent("rooms", message))
                    elif message["Command"] == "Game_Started":
                        QCoreApplication.postEvent(self, MessageEvent("start_game",message))
                    else:
                        QCoreApplication.postEvent(self, MessageEvent("status", f"Unknown command received: {message['Command']}"))
            except socket.error as e:
                if self.running and e.errno == errno.WSAEWOULDBLOCK:
                    continue
                if self.running:
                    QCoreApplication.postEvent(self, MessageEvent("status", f"Error receiving message: {e}"))
                    self.disconnect()
                break

    def customEvent(self, event):
        if event.type() == MessageEvent.EventType:
            if event.message_type == "chat":
                self.process_chat_update(event.data)
            elif event.message_type == "rooms":
                self.process_rooms_update(event.data)
            elif event.message_type == "status":
                self.process_status_update(event.data)
            elif event.message_type == "start_game":
                self.start_game(event.data)
                
    # Start the game with the received message
    def start_game(self, message):
        print(f"Game started with message:", message)
        # Set game running state to True
        self.game_running = True        
        
        # Send game running state to server  
        game_state_message = {
            "Command": "Game_State_Update",
            "Room_Name": self.room_name,
            "User_Name": self.username,
            "Game_Running": True
        }
        try:
            data = pickle.dumps(game_state_message)
            client_menu.client_socket.sendall(data)
        except Exception as e:
            print(f"Error sending game state: {e}")
        
        # Start the actual Connect 4 game
        try:
            from game import main
            # Pass player assignment from server
            player_assignment = message.get("Player_Assignment", {})
            main(self.client_socket, self.username, self.list_of_users_in_room, self.room_name, player_assignment)
        except Exception as e:
            print(f"Error starting game: {e}")
        
        # After game ends, set game running to False
        self.game_running = False
        
        # Send game end state to server
        game_end_message = {
            "Command": "Game_State_Update", 
            "Room_Name": self.room_name,
            "User_Name": self.username,
            "Game_Running": False
        }
        try:
            data = pickle.dumps(game_end_message)
            client_menu.client_socket.sendall(data)
        except Exception as e:
            print(f"Error sending game end state: {e}")
        
        # Update the lobby display when returning from game
        if self.chatroom and self.chatroom.room_name == self.room_name:
            self.chatroom.update_players_display()
            self.chatroom.chat_display.append("<span style='color: #f39c12;'>🔄 Returned to lobby from game</span>")
        
        
    def process_chat_update(self, message):
        print(f"Processing chat message: {message}")
        try:
            if message["Command"] == "Join_Room":
                room_name = message["Room_Name"]
                list_of_users = message["Users_In_Room"]
                self.list_of_users_in_room = list_of_users
                self.room_name = room_name
                # Check if already in a room
                if self.alreadyinroom == False:
                    # If not already in a room, create a new chatroom
                    if self.chatroom:
                        #Close the existing chatroom if it exists
                        self.chatroom.close()
                    self.chatroom = GameLobby(self.username, room_name, list_of_users, self.client_socket)   
                    self.alreadyinroom = True
                else:
                    # If already in a room, just update the chatroom
                    if self.chatroom and self.chatroom.room_name == room_name:
                        self.chatroom.list_of_users_in_room = list_of_users
                        self.chatroom.update_players_display()
                        
            elif message["Command"] == "Sending_Message":
                room_name = message["Room_Name"]
                text = message["Text"]
                username = message["User_Name"]
                if self.chatroom and self.chatroom.room_name == room_name:
                    self.chatroom.updating_text_edit(f"{username}: {text}", self.list_of_users_in_room)
                    
            elif message["Command"] == "Player_Ready":
                if self.chatroom and self.chatroom.room_name == message["Room_Name"]:
                    self.chatroom.handle_ready_status(message["User_Name"], message["Ready_Status"])
                    
            # Handle game state updates
            elif message["Command"] == "Game_State_Update":
                if self.chatroom and self.chatroom.room_name == message["Room_Name"]:
                    self.chatroom.handle_game_state_update(message)
                    
            elif message["Command"] == "game_ended_player_left":
                if self.chatroom and self.chatroom.room_name == message["room_name"]:
                    left_player = message.get("left_player", "")
                    winner = message.get("winner", "")
                    
                    if winner == self.username:
                        win_msg = f"🎉 You win! {left_player} left the game."
                    else:
                        win_msg = f"🚪 {left_player} left the game. {winner} wins!"
                    
                    self.chatroom.chat_display.append(f"<span style='color: #27ae60;'>{win_msg}</span>")
                    self.chatroom.handle_game_state_update({"Game_Running": False})
        except Exception as e:
            QCoreApplication.postEvent(self, MessageEvent("status", f"Error processing chat message: {e}"))

    def process_rooms_update(self, message):
        print(f"Processing room update: {message}")
        try:
            if message["Command"] == "Check_Username":
                self.list_of_users_in_room = message["Users_In_Room"]
                self.create_room_button.setEnabled(True)
                self.join_room_button.setEnabled(True)
                self.send_message({
                    "Command": "Request_Room_State",
                    "User_Name": self.username,
                    "Users_In_Room": self.list_of_users_in_room
                })
                
            elif message["Command"] == "Room_State":
                # Limit to max 4 rooms
                available_rooms = list(message["Available_Rooms"])[:4]
                
                if message["Users_In_Room"]: 
                    self.list_of_users_in_room = message["Users_In_Room"]
                self.list_of_available_rooms = available_rooms
                self.update_rooms_display()
                #After updating rooms, delete the room input text
                self.room_input.clear()
                self.room_input.setPlaceholderText("🔴 Enter room name")
                
        except Exception as e:
            QCoreApplication.postEvent(self, MessageEvent("status", f"Error processing room update: {e}"))

    def process_status_update(self, message):
        print(f"Processing status update: {message}")
        if "Error" in message:
            QMessageBox.critical(self, "Error", message)
        elif "disconnected" in message.lower():
            QMessageBox.warning(self, "Connection", message)
            self.disconnect()

    def Create_room(self):
        current_room = self.room_input.text().strip()
        if len(self.list_of_available_rooms) >= 4:
            self.room_input.setPlaceholderText("Maximum of 4 rooms allowed!")
            return
            
        if current_room:
            message = {
                "Command": "Create_Room",
                "Room_Name": current_room,
                "User_Name": self.username
            }
            self.send_message(message)
        else:
            self.room_input.setPlaceholderText("An input is required to create a room")
            
    def Join_room(self):
        current_room = self.room_input.text().strip()
        if current_room:
            message = {
                "Command": "Join_Room",
                "Room_Name": current_room,
                "User_Name": self.username
            }
            self.send_message(message)
            self.send_message({
                "Command": "Request_Room_State",
                "User_Name": self.username
            })
            self.send_message({
                "Command": "Sending_Message",
                "Room_Name": current_room,
                "User_Name": self.username,
                "Text": f"{self.username} has joined the game!"
            })
        else:
            self.room_input.setPlaceholderText("Please enter a room name to join or Create a new room")
                
    def send_message(self, message):
        if self.client_socket and self.running and not self.is_disconnected:
            try:
                print (f"Sending message: {message}")
                # Ensure socket is in blocking mode
                self.client_socket.setblocking(True)
                data = pickle.dumps(message)
                self.client_socket.sendall(data)
            except socket.error as e:
                if e.errno == errno.WSAEWOULDBLOCK:
                    pass
                else:
                    QCoreApplication.postEvent(self, MessageEvent("status", f"Error sending message: {e}"))
                    self.disconnect()
            except Exception as e:
                QCoreApplication.postEvent(self, MessageEvent("status", f"Error sending message: {e}"))
                self.disconnect()

    def closeEvent(self, event):
        self.disconnect()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client_menu = GameMainMenu("127.0.0.1", 12345)
    client_menu.show()
    sys.exit(app.exec_())