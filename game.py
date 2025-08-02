import pygame
import sys
import pickle
import threading
import socket
from enum import Enum
import math
import random

# Initialize Pygame
pygame.init()

# Constants
BOARD_WIDTH = 7
BOARD_HEIGHT = 7
CELL_SIZE = 80
BOARD_OFFSET_X = 50
BOARD_OFFSET_Y = 150
WINDOW_WIDTH = BOARD_WIDTH * CELL_SIZE + 2 * BOARD_OFFSET_X
WINDOW_HEIGHT = BOARD_HEIGHT * CELL_SIZE + 2 * BOARD_OFFSET_Y + 100

# Colors (Dark Theme)
DARK_BG = (25, 25, 35)
DARKER_BG = (18, 18, 25)
BOARD_COLOR = (45, 50, 65)
EMPTY_CELL = (60, 65, 80)
PLAYER1_COLOR = (220, 50, 50)  # Red
PLAYER2_COLOR = (255, 215, 0)  # Gold
HOVER_COLOR = (100, 110, 130)
TEXT_COLOR = (230, 230, 240)
SUCCESS_COLOR = (50, 200, 50)
ERROR_COLOR = (200, 50, 50)
BORDER_COLOR = (80, 85, 100)

# Fonts
font_large = pygame.font.Font(None, 48)
font_medium = pygame.font.Font(None, 36)
font_small = pygame.font.Font(None, 24)

class GameState(Enum):
    WAITING = 1
    PLAYING = 2
    GAME_OVER = 3

class Connect4Game:
    def __init__(self, client_socket, username, list_of_users_in_room, room_name, player_assignment=None):
        self.client_socket = client_socket
        self.username = username
        self.list_of_users_in_room = list_of_users_in_room
        self.room_name = room_name
        self.running = True
        
        # Game state
        self.board = [[0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.current_player = 1
        self.game_state = GameState.PLAYING  # Start in playing state since game was started from lobby
        self.winner = None
        self.hover_col = -1
        
        # Player mapping - Use server assignment or fallback to index-based
        if player_assignment:
            self.player_number = player_assignment.get(self.username, 1)
            print(f"Server assigned player number: {self.player_number}")
        else:
            self.player_number = self.get_player_number()
            print(f"Fallback player number: {self.player_number}")
        
        self.opponent = self.get_opponent()
        
        # UI elements
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(f"Connect 4 - {room_name}")
        self.clock = pygame.time.Clock()
        
        # Messages
        self.status_message = f"Game Started! Player 1 goes first"
        self.message_timer = 180
        
        # Animation
        self.dropping_piece = None  # (col, row, color, y_pos)
        self.drop_speed = 8
        
        print(f"Connect 4 initialized for {username} (Player {self.player_number}) in room {room_name}")
        print(f"Opponent: {self.opponent}")
        
        # Start message receiver thread
        threading.Thread(target=self.receive_messages, daemon=True).start()

    def get_player_number(self):
        """Determine which player number this client is (1 or 2)"""
        try:
            return self.list_of_users_in_room.index(self.username) + 1
        except (ValueError, AttributeError):
            return 1

    def get_opponent(self):
        """Get opponent's username"""
        if not self.list_of_users_in_room:
            return None
        for user in self.list_of_users_in_room:
            if user != self.username:
                return user
        return None

    def receive_messages(self):
        """Receive messages from server in separate thread"""
        while self.running:
            try:
                data = self.client_socket.recv(1048576)
                if not data:
                    break
                message = pickle.loads(data)
                self.handle_server_message(message)
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

    def handle_server_message(self, message):
        """Handle messages from server"""
        command = message.get("Command", "")
        
        if command == "game_move":
            col = message["col"]
            player = message["player"]
            move_username = message["username"]
            
            # Always apply moves from server (server is the authority)
            print(f"Applying server move: column {col}, player {player} from {move_username}")
            self.make_move(col, player, from_server=True)
            
        elif command == "game_start":
            self.game_state = GameState.PLAYING
            self.current_player = 1
            if len(self.list_of_users_in_room) >= 2:
                self.status_message = f"Game Started! Player 1 ({self.list_of_users_in_room[0]}) goes first"
            else:
                self.status_message = "Game Started! Player 1 goes first"
            self.message_timer = 180
            
        elif command == "game_reset":
            self.reset_game()
            
        elif command == "player_disconnect":
            disconnected_player = message.get("username", "")
            self.status_message = f"{disconnected_player} disconnected. Game ended."
            self.game_state = GameState.GAME_OVER
            self.message_timer = 300
            
        elif command == "turn_update":
            # Server can send turn updates to synchronize game state
            new_current_player = message.get("current_player", self.current_player)
            self.current_player = new_current_player
            
            if len(self.list_of_users_in_room) >= self.current_player:
                current_player_name = self.list_of_users_in_room[self.current_player - 1]
                self.status_message = f"Player {self.current_player} ({current_player_name})'s turn"
            else:
                self.status_message = f"Player {self.current_player}'s turn"
            self.message_timer = 120
        elif command == "game_ended_player_left":
            left_player = message.get("left_player", "")
            winner = message.get("winner", "")
            
            if winner == self.username:
                self.status_message = f"🎉 You win! {left_player} left the game."
            else:
                self.status_message = f"🚪 {left_player} left the game. {winner} wins!"
            
            self.game_state = GameState.GAME_OVER
            self.winner = message.get("winner")
            self.message_timer = 300
        
        
        
    def send_move(self, col):
        """Send move to server"""
        message = {
            "Command": "game_move",
            "room_name": self.room_name,
            "username": self.username,
            "col": col,
            "player": self.player_number
        }
        try:
            data = pickle.dumps(message)
            self.client_socket.sendall(data)
            print(f"Sent move: column {col}, player {self.player_number}")
        except Exception as e:
            print(f"Error sending move: {e}")

    def send_game_reset(self):
        """Send game reset signal to server"""
        message = {
            "Command": "game_reset",
            "room_name": self.room_name,
            "username": self.username
        }
        try:
            data = pickle.dumps(message)
            self.client_socket.sendall(data)
        except Exception as e:
            print(f"Error sending game reset: {e}")

    def make_move(self, col, player, from_server=False):
        """Make a move on the board"""
        if self.game_state != GameState.PLAYING:
            return False
            
        # Find the lowest empty row in the column
        for row in range(BOARD_HEIGHT - 1, -1, -1):
            if self.board[row][col] == 0:
                self.board[row][col] = player
                
                # Start drop animation
                color = PLAYER1_COLOR if player == 1 else PLAYER2_COLOR
                self.dropping_piece = (col, row, color, 0)
                
                # Check for win
                if self.check_win(row, col, player):
                    self.winner = player
                    self.game_state = GameState.GAME_OVER
                    if len(self.list_of_users_in_room) >= player:
                        winner_name = self.list_of_users_in_room[player - 1]
                        self.status_message = f"🎉 {winner_name} wins!"
                    else:
                        self.status_message = f"🎉 Player {player} wins!"
                    self.message_timer = 300
                    return True
                
                # Check for draw
                if self.is_board_full():
                    self.game_state = GameState.GAME_OVER
                    self.status_message = "It's a draw!"
                    self.message_timer = 300
                    return True
                
                # Switch players
                self.current_player = 2 if self.current_player == 1 else 1
                if len(self.list_of_users_in_room) >= self.current_player:
                    current_player_name = self.list_of_users_in_room[self.current_player - 1]
                    self.status_message = f"Player {self.current_player} ({current_player_name})'s turn"
                else:
                    self.status_message = f"Player {self.current_player}'s turn"
                self.message_timer = 120
                return True
        
        return False

    def check_win(self, row, col, player):
        """Check if the current move resulted in a win"""
        directions = [
            (0, 1),   # Horizontal
            (1, 0),   # Vertical
            (1, 1),   # Diagonal /
            (1, -1)   # Diagonal \
        ]
        
        for dx, dy in directions:
            count = 1
            
            # Check positive direction
            r, c = row + dx, col + dy
            while 0 <= r < BOARD_HEIGHT and 0 <= c < BOARD_WIDTH and self.board[r][c] == player:
                count += 1
                r, c = r + dx, c + dy
            
            # Check negative direction
            r, c = row - dx, col - dy
            while 0 <= r < BOARD_HEIGHT and 0 <= c < BOARD_WIDTH and self.board[r][c] == player:
                count += 1
                r, c = r - dx, c - dy
            
            if count >= 4:
                return True
        
        return False

    def is_board_full(self):
        """Check if the board is full"""
        return all(self.board[0][col] != 0 for col in range(BOARD_WIDTH))

    def is_valid_move(self, col):
        """Check if a move is valid"""
        return 0 <= col < BOARD_WIDTH and self.board[0][col] == 0

    def reset_game(self):
        """Reset the game to initial state"""
        self.board = [[0 for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]
        self.current_player = 1
        self.game_state = GameState.PLAYING
        self.winner = None
        self.dropping_piece = None
        self.status_message = "Game reset! Player 1 goes first"
        self.message_timer = 120

    def get_cell_center(self, row, col):
        """Get the center coordinates of a cell"""
        x = BOARD_OFFSET_X + col * CELL_SIZE + CELL_SIZE // 2
        y = BOARD_OFFSET_Y + row * CELL_SIZE + CELL_SIZE // 2
        return x, y

    def get_column_from_mouse(self, mouse_x):
        """Get column from mouse x position"""
        if BOARD_OFFSET_X <= mouse_x <= BOARD_OFFSET_X + BOARD_WIDTH * CELL_SIZE:
            return (mouse_x - BOARD_OFFSET_X) // CELL_SIZE
        return -1

    def draw_board(self):
        """Draw the game board"""
        # Draw board background
        board_rect = pygame.Rect(
            BOARD_OFFSET_X - 10, 
            BOARD_OFFSET_Y - 10, 
            BOARD_WIDTH * CELL_SIZE + 20, 
            BOARD_HEIGHT * CELL_SIZE + 20
        )
        pygame.draw.rect(self.screen, BOARD_COLOR, board_rect)
        pygame.draw.rect(self.screen, BORDER_COLOR, board_rect, 3)
        
        # Draw cells
        for row in range(BOARD_HEIGHT):
            for col in range(BOARD_WIDTH):
                x, y = self.get_cell_center(row, col)
                
                # Draw cell background
                cell_rect = pygame.Rect(
                    BOARD_OFFSET_X + col * CELL_SIZE + 5,
                    BOARD_OFFSET_Y + row * CELL_SIZE + 5,
                    CELL_SIZE - 10,
                    CELL_SIZE - 10
                )
                
                # Highlight hovered column
                if col == self.hover_col and self.game_state == GameState.PLAYING and self.current_player == self.player_number:
                    pygame.draw.rect(self.screen, HOVER_COLOR, cell_rect)
                else:
                    pygame.draw.rect(self.screen, EMPTY_CELL, cell_rect)
                
                pygame.draw.rect(self.screen, BORDER_COLOR, cell_rect, 2)
                
                # Draw piece if present
                if self.board[row][col] != 0:
                    color = PLAYER1_COLOR if self.board[row][col] == 1 else PLAYER2_COLOR
                    pygame.draw.circle(self.screen, color, (x, y), CELL_SIZE // 2 - 15)
                    pygame.draw.circle(self.screen, BORDER_COLOR, (x, y), CELL_SIZE // 2 - 15, 3)

    def draw_dropping_piece(self):
        """Draw animated dropping piece"""
        if self.dropping_piece:
            col, target_row, color, y_pos = self.dropping_piece
            
            # Calculate target position
            target_y = BOARD_OFFSET_Y + target_row * CELL_SIZE + CELL_SIZE // 2
            start_y = BOARD_OFFSET_Y - CELL_SIZE // 2
            
            # Update animation
            if y_pos < target_y - start_y:
                y_pos += self.drop_speed
                self.drop_speed += 0.5  # Gravity effect
            else:
                # Animation finished
                self.dropping_piece = None
                self.drop_speed = 8
                return
            
            # Draw the piece
            x = BOARD_OFFSET_X + col * CELL_SIZE + CELL_SIZE // 2
            actual_y = start_y + y_pos
            pygame.draw.circle(self.screen, color, (int(x), int(actual_y)), CELL_SIZE // 2 - 15)
            pygame.draw.circle(self.screen, BORDER_COLOR, (int(x), int(actual_y)), CELL_SIZE // 2 - 15, 3)
            
            # Update the animation
            self.dropping_piece = (col, target_row, color, y_pos)

    def draw_ui(self):
        """Draw UI elements"""
        # Title
        title_text = font_large.render(f"Connect 4 - {self.room_name}", True, TEXT_COLOR)
        title_rect = title_text.get_rect(center=(WINDOW_WIDTH // 2, 30))
        self.screen.blit(title_text, title_rect)
        
        # Player info
        y_offset = 70
        for i, player_name in enumerate(self.list_of_users_in_room[:2]):  # Only show first 2 players
            player_num = i + 1
            color = PLAYER1_COLOR if player_num == 1 else PLAYER2_COLOR
            
            # Player indicator
            indicator_text = f"Player {player_num}: {player_name}"
            if player_name == self.username:
                indicator_text += " (You)"
            
            # Highlight current player
            if self.current_player == player_num and self.game_state == GameState.PLAYING:
                text_color = SUCCESS_COLOR
                if player_name == self.username:
                    indicator_text += " ← Your turn!"
                else:
                    indicator_text += " ← Their turn"
            else:
                text_color = TEXT_COLOR
            
            text = font_medium.render(indicator_text, True, text_color)
            
            # Draw colored circle next to player name
            circle_x = 20
            circle_y = y_offset + i * 30 + 10
            pygame.draw.circle(self.screen, color, (circle_x, circle_y), 12)
            pygame.draw.circle(self.screen, BORDER_COLOR, (circle_x, circle_y), 12, 2)
            
            self.screen.blit(text, (45, y_offset + i * 30))
        
        # Status message
        if self.message_timer > 0:
            status_color = SUCCESS_COLOR if "wins" in self.status_message or "Started" in self.status_message else TEXT_COLOR
            if "disconnected" in self.status_message:
                status_color = ERROR_COLOR
            
            status_text = font_medium.render(self.status_message, True, status_color)
            status_rect = status_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 40))
            self.screen.blit(status_text, status_rect)
            self.message_timer -= 1
        
        # Instructions
        if self.game_state == GameState.PLAYING:
            if self.current_player == self.player_number:
                instruction = "Click a column to drop your piece"
            else:
                instruction = "Waiting for opponent's move..."
        else:  # GAME_OVER
            instruction = "Press R to reset game or ESC to return to lobby"
        
        instruction_text = font_small.render(instruction, True, TEXT_COLOR)
        instruction_rect = instruction_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 15))
        self.screen.blit(instruction_text, instruction_rect)

    def handle_click(self, mouse_x):
        """Handle mouse click"""
        if self.game_state != GameState.PLAYING:
            return
        
        if self.current_player != self.player_number:
            return  # Not our turn
        
        col = self.get_column_from_mouse(mouse_x)
        if col != -1 and self.is_valid_move(col):
            # Only send to server, don't make move locally
            self.send_move(col)

    def run(self):
        """Main game loop"""
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # Left click
                        self.handle_click(event.pos[0])
                
                elif event.type == pygame.MOUSEMOTION:
                    # Update hover column only if it's our turn
                    if self.game_state == GameState.PLAYING and self.current_player == self.player_number:
                        self.hover_col = self.get_column_from_mouse(event.pos[0])
                    else:
                        self.hover_col = -1
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        if self.game_state == GameState.GAME_OVER:
                            self.send_game_reset()
                    
                    elif event.key == pygame.K_ESCAPE:
                        # Send player left game message to server
                        leave_game_message = {
                            "Command": "player_left_game",
                            "room_name": self.room_name,
                            "username": self.username
                        }
                        try:
                            data = pickle.dumps(leave_game_message)
                            self.client_socket.sendall(data)
                        except Exception as e:
                            print(f"Error sending leave game message: {e}")
                            # Return to lobby
                            self.running = False
                                        
            # Clear screen
            self.screen.fill(DARK_BG)
            
            # Draw game elements
            self.draw_board()
            self.draw_dropping_piece()
            self.draw_ui()
            
            # Update display
            pygame.display.flip()
            self.clock.tick(60)
        
        pygame.quit()

def main(client_socket, username, list_of_users_in_room, room_name, player_assignment=None):
    """Main function to start the Connect 4 game"""
    print(f"Starting Connect 4 game for {username} in room {room_name}")
    print(f"Players: {list_of_users_in_room}")
    print(f"Player assignment: {player_assignment}")
    
    game = Connect4Game(client_socket, username, list_of_users_in_room, room_name, player_assignment)
    game.run()

if __name__ == "__main__":
    # For testing purposes
    print("This module should be imported and called from the main client")