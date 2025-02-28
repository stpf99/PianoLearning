import os
import sys
import time
import mido
import pygame
import pygame.midi
import rtmidi
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QPainter, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QGroupBox, QDialog, QDialogButtonBox, QSpinBox, QSlider, QLineEdit
)

class PianoLearningApp(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Piano Learning App")
        self.setGeometry(100, 100, 1200, 700)
        
        # Configuration
        self.midi_directory = "midi_songs"  # Default directory
        self.accuracy_threshold = 80  # Default accuracy percentage
        self.num_keys = 48  # Piano roll size
        self.start_note = 36  # MIDI note number for the lowest key (C2)
        
        # MIDI variables
        self.midi_input = None
        self.midi_output = None
        self.midi_file = None
        self.playing_notes = set()
        self.expected_notes = set()
        self.note_events = []
        self.current_time = 0
        self.score = 0
        self.max_possible_score = 0
        self.stream_speed = 100  # Pixels per second
        self.is_playing = False
        self.is_paused = False
        self.is_previewing = False
        self.pause_time = 0
        
        # Initialize pygame and pygame.midi
        pygame.init()
        pygame.midi.init()
        
        # Initialize rtmidi output
        self.rtmidi_output = None
        self.setup_rtmidi_output()
        
        # Load the UI
        self.init_ui()
        
        # Set up timer for playback
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_playback)
        self.timer.start(30)  # Update every 30ms
        
    def setup_rtmidi_output(self):
        try:
            self.rtmidi_output = rtmidi.MidiOut()
            available_ports = self.rtmidi_output.get_ports()
            if available_ports:
                self.rtmidi_output.open_port(0)
                print("Opened rtmidi output:", available_ports[0])
            else:
                self.rtmidi_output.open_virtual_port("PianoLearningApp Output")
                print("Created virtual rtmidi output port")
        except Exception as e:
            print("Error opening rtmidi output:", e)
        
    def init_ui(self):
        # Main widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create note stream canvas
        self.note_canvas = NoteStreamCanvas(self)
        self.note_canvas.setMinimumHeight(300)
        main_layout.addWidget(self.note_canvas)
        
        # Create piano keyboard display
        self.piano_display = PianoKeyboardWidget(self.num_keys, self.start_note)
        self.piano_display.setMinimumHeight(120)
        main_layout.addWidget(self.piano_display)
        
        # Create control panel
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Status bar for messages
        self.statusBar().showMessage("Ready")
        
        # Initialize MIDI devices
        self.refresh_midi_devices()
        
    def create_menu_bar(self):
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("File")
        
        open_action = QAction("Open MIDI File", self)
        open_action.triggered.connect(self.load_midi_file)
        file_menu.addAction(open_action)
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.show_settings)
        file_menu.addAction(settings_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menu_bar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def create_control_panel(self):
        control_panel = QGroupBox("Controls")
        control_layout = QVBoxLayout(control_panel)
        
        # MIDI input device selection
        input_device_layout = QHBoxLayout()
        input_device_layout.addWidget(QLabel("MIDI Input Device:"))
        
        self.midi_input_combo = QComboBox()
        self.midi_input_combo.currentIndexChanged.connect(self.select_midi_input)
        input_device_layout.addWidget(self.midi_input_combo)
        
        control_layout.addLayout(input_device_layout)
        
        # MIDI output device selection
        output_device_layout = QHBoxLayout()
        output_device_layout.addWidget(QLabel("MIDI Output Device:"))
        
        self.midi_output_combo = QComboBox()
        self.midi_output_combo.currentIndexChanged.connect(self.select_midi_output)
        output_device_layout.addWidget(self.midi_output_combo)
        
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_midi_devices)
        output_device_layout.addWidget(refresh_button)
        
        control_layout.addLayout(output_device_layout)
        
        # Playback controls
        playback_layout = QHBoxLayout()
        
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.start_playing)
        playback_layout.addWidget(self.play_button)
        
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.pause_playing)
        self.pause_button.setEnabled(False)
        playback_layout.addWidget(self.pause_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playing)
        self.stop_button.setEnabled(False)
        playback_layout.addWidget(self.stop_button)
        
        self.preview_button = QPushButton("Preview")
        self.preview_button.clicked.connect(self.toggle_preview)
        playback_layout.addWidget(self.preview_button)
        
        control_layout.addLayout(playback_layout)
        
        # Song info and score
        info_layout = QHBoxLayout()
        
        self.song_label = QLabel("No song loaded")
        info_layout.addWidget(self.song_label)
        
        info_layout.addStretch(1)
        
        self.score_label = QLabel("Score: 0%")
        info_layout.addWidget(self.score_label)
        
        control_layout.addLayout(info_layout)
        
        return control_panel
    
    def refresh_midi_devices(self):
        # Remember currently selected devices
        current_input = self.midi_input_combo.currentText() if self.midi_input_combo.currentIndex() >= 0 else ""
        current_output = self.midi_output_combo.currentText() if self.midi_output_combo.currentIndex() >= 0 else ""
        
        # Clear lists
        self.midi_input_combo.clear()
        self.midi_output_combo.clear()
        
        # Add "None" option
        self.midi_input_combo.addItem("None")
        self.midi_output_combo.addItem("None")
        
        # Check for USB MIDI devices using rtmidi
        try:
            midi_in = rtmidi.MidiIn()
            midi_out = rtmidi.MidiOut()
            
            # Add rtmidi ports
            for port_idx, port_name in enumerate(midi_in.get_ports()):
                device_str = f"rtmidi: {port_name}"
                self.midi_input_combo.addItem(device_str, ("rtmidi", port_idx))
            
            for port_idx, port_name in enumerate(midi_out.get_ports()):
                device_str = f"rtmidi: {port_name}"
                self.midi_output_combo.addItem(device_str, ("rtmidi", port_idx))
                
            midi_in.delete()
            midi_out.delete()
        except Exception as e:
            print(f"Error listing rtmidi devices: {e}")
        
        # Get available pygame MIDI devices
        try:
            for i in range(pygame.midi.get_count()):
                info = pygame.midi.get_device_info(i)
                name = info[1].decode('utf-8')
                is_input = info[2]
                is_output = info[3]
                is_opened = info[4]
                
                device_str = f"pygame: {name} (ID: {i})"
                
                if is_input and not is_opened:
                    self.midi_input_combo.addItem(device_str, ("pygame", i))
                
                if is_output and not is_opened:
                    self.midi_output_combo.addItem(device_str, ("pygame", i))
        except Exception as e:
            print(f"Error listing pygame MIDI devices: {e}")
        
        # Restore previous selections if they exist
        if current_input:
            index = self.midi_input_combo.findText(current_input)
            if index >= 0:
                self.midi_input_combo.setCurrentIndex(index)
        
        if current_output:
            index = self.midi_output_combo.findText(current_output)
            if index >= 0:
                self.midi_output_combo.setCurrentIndex(index)
        
        # Display found devices in status bar
        if self.midi_input_combo.count() > 1 or self.midi_output_combo.count() > 1:
            self.statusBar().showMessage(f"Found {self.midi_input_combo.count()-1} input and {self.midi_output_combo.count()-1} output MIDI devices")
        else:
            self.statusBar().showMessage("No MIDI devices found. Try connecting a MIDI keyboard and click Refresh.")

    def select_midi_input(self, index):
        if index <= 0:  # "None" option or invalid selection
            if self.midi_input is not None:
                self.midi_input.close_port()
                self.midi_input = None
            return
        
        try:
            data = self.midi_input_combo.itemData(index)
            if not data:
                return
                
            device_type, device_id = data
            device_name = self.midi_input_combo.currentText()
            
            # Close existing MIDI input if open
            if self.midi_input is not None:
                self.midi_input.close_port()
                self.midi_input = None
            
            if device_type == "rtmidi":
                self.midi_input = rtmidi.MidiIn()
                self.midi_input.open_port(device_id)
                
                # Set up callback for MIDI input events
                def midi_callback(message, time_stamp):
                    data = message[0]
                    if data[0] & 0xF0 == 0x90:  # Note on
                        note = data[1]
                        velocity = data[2]
                        if velocity > 0:
                            self.handle_note_on(note, velocity)
                        else:
                            self.handle_note_off(note)
                    elif data[0] & 0xF0 == 0x80:  # Note off
                        note = data[1]
                        self.handle_note_off(note)
                
                self.midi_input.set_callback(midi_callback)
            
            elif device_type == "pygame":
                self.midi_input = pygame.midi.Input(device_id)
                # We'll poll this in the timer
            
            self.statusBar().showMessage(f"Connected to MIDI input device: {device_name}")
            
        except Exception as e:
            self.statusBar().showMessage(f"Error connecting to MIDI input device: {e}")
            if self.midi_input is not None:
                self.midi_input.close_port()
                self.midi_input = None

    def select_midi_output(self, index):
        if index <= 0:  # "None" option or invalid selection
            if self.midi_output is not None:
                if isinstance(self.midi_output, rtmidi.MidiOut):
                    self.midi_output.close_port()
                else:
                    self.midi_output.close()
                self.midi_output = None
            return
        
        try:
            data = self.midi_output_combo.itemData(index)
            if not data:
                return
                
            device_type, device_id = data
            device_name = self.midi_output_combo.currentText()
            
            # Close existing MIDI output if open
            if self.midi_output is not None:
                if isinstance(self.midi_output, rtmidi.MidiOut):
                    self.midi_output.close_port()
                else:
                    self.midi_output.close()
                self.midi_output = None
            
            if device_type == "rtmidi":
                self.midi_output = rtmidi.MidiOut()
                self.midi_output.open_port(device_id)
            elif device_type == "pygame":
                self.midi_output = pygame.midi.Output(device_id)
            
            self.statusBar().showMessage(f"Connected to MIDI output device: {device_name}")
            
        except Exception as e:
            self.statusBar().showMessage(f"Error connecting to MIDI output device: {e}")
            if self.midi_output is not None:
                if isinstance(self.midi_output, rtmidi.MidiOut):
                    self.midi_output.close_port()
                else:
                    self.midi_output.close()
                self.midi_output = None

    def handle_note_on(self, note, velocity):
        # Update piano display
        self.piano_display.note_on(note)
        
        # Forward to the selected MIDI output
        if self.midi_output:
            if isinstance(self.midi_output, rtmidi.MidiOut):
                self.midi_output.send_message([0x90, note, velocity])
            else:  # pygame.midi.Output
                self.midi_output.note_on(note, velocity)
        
        # Also forward to the rtmidi_output (separate output)
        if self.rtmidi_output:
            self.rtmidi_output.send_message([0x90, note, velocity])
        
        # Check if note is expected
        if self.is_playing and not self.is_previewing:
            if note in self.expected_notes:
                self.score += 1
                self.update_score()
        
        # Add to currently playing notes
        self.playing_notes.add(note)
    
    def handle_note_off(self, note):
        # Update piano display
        self.piano_display.note_off(note)
        
        # Forward to the selected MIDI output
        if self.midi_output:
            if isinstance(self.midi_output, rtmidi.MidiOut):
                self.midi_output.send_message([0x80, note, 0])
            else:  # pygame.midi.Output
                self.midi_output.note_off(note, 0)
        
        # Also forward to the rtmidi_output (separate output)
        if self.rtmidi_output:
            self.rtmidi_output.send_message([0x80, note, 0])
        
        # Remove from currently playing notes
        if note in self.playing_notes:
            self.playing_notes.remove(note)
    
    def load_midi_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open MIDI File", self.midi_directory, "MIDI Files (*.mid *.midi)"
        )
        
        if not file_path:
            return
        
        try:
            self.midi_file = mido.MidiFile(file_path)
            self.midi_directory = os.path.dirname(file_path)
            
            # Extract song name from file path
            song_name = os.path.basename(file_path)
            self.song_label.setText(f"Song: {song_name}")
            
            # Process MIDI file to extract note events
            self.process_midi_file()
            
            # Reset playback state
            self.stop_playing()
            
            # Enable play button
            self.play_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            
            self.statusBar().showMessage(f"Loaded MIDI file: {song_name}")
        except Exception as e:
            self.statusBar().showMessage(f"Error loading MIDI file: {e}")
    
    def process_midi_file(self):
        if not self.midi_file:
            return
        
        # Extract note events from all tracks
        self.note_events = []
        tempo = get_tempo(self.midi_file)
        
        active_notes = {}  # Track active notes to ensure proper note_off events
        
        for track in self.midi_file.tracks:
            track_time = 0
            for msg in track:
                track_time += msg.time
                seconds = mido.tick2second(track_time, self.midi_file.ticks_per_beat, tempo)
                
                if msg.type == 'note_on' and hasattr(msg, 'velocity'):
                    note = msg.note
                    
                    if msg.velocity > 0:
                        # Note on event
                        self.note_events.append({
                            'type': 'note_on',
                            'note': note,
                            'velocity': msg.velocity,
                            'time': seconds
                        })
                        
                        # Track this as an active note
                        active_notes[note] = seconds
                    else:
                        # Note off event (velocity=0)
                        self.note_events.append({
                            'type': 'note_off',
                            'note': note,
                            'velocity': 0,
                            'time': seconds
                        })
                        
                        # Remove from active notes
                        if note in active_notes:
                            del active_notes[note]
                
                elif msg.type == 'note_off':
                    note = msg.note
                    
                    self.note_events.append({
                        'type': 'note_off',
                        'note': note,
                        'velocity': 0,
                        'time': seconds
                    })
                    
                    # Remove from active notes
                    if note in active_notes:
                        del active_notes[note]
                
                elif msg.type == 'set_tempo':
                    # Update tempo for subsequent events
                    tempo = msg.tempo
        
        # Add note_off events for any notes still active at the end of the track
        # (Some MIDI files might not properly close all notes)
        for note, start_time in active_notes.items():
            self.note_events.append({
                'type': 'note_off',
                'note': note,
                'velocity': 0,
                'time': start_time + 2  # Add 2 seconds as a fallback duration
            })
        
        # Sort events by time
        self.note_events = sorted(self.note_events, key=lambda x: x['time'])
        
        # Set the maximum possible score
        self.max_possible_score = len([e for e in self.note_events if e['type'] == 'note_on'])
        
        # Update the note canvas
        self.note_canvas.set_note_events(self.note_events)
    
    def start_playing(self):
        if not self.midi_file:
            return
        
        if self.is_paused:
            # Resume from pause
            self.is_paused = False
            self.current_time += time.time() - self.pause_time
        else:
            # Start from beginning
            self.current_time = time.time()
            self.score = 0
            self.expected_notes = set()
        
        self.is_playing = True
        
        # Update UI
        self.play_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.preview_button.setEnabled(False)
        
        self.statusBar().showMessage("Playing...")
    
    def pause_playing(self):
        if self.is_playing:
            self.is_playing = False
            self.is_paused = True
            self.pause_time = time.time()
            
            # Update UI
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.statusBar().showMessage("Paused")
    
    def stop_playing(self):
        self.is_playing = False
        self.is_paused = False
        self.expected_notes = set()
        
        # Reset UI
        self.note_canvas.reset_playback()
        self.piano_display.reset()
        
        # Turn off all notes in MIDI output
        self.all_notes_off()
        
        # Update UI controls
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.preview_button.setEnabled(self.midi_file is not None)
        
        self.statusBar().showMessage("Stopped")
    
    def all_notes_off(self):
        # Turn off all notes in all outputs
        for note in range(128):
            # Turn off in the selected MIDI output
            if self.midi_output:
                if isinstance(self.midi_output, rtmidi.MidiOut):
                    self.midi_output.send_message([0x80, note, 0])
                else:  # pygame.midi.Output
                    self.midi_output.note_off(note, 0)
            
            # Turn off in the separate rtmidi output
            if self.rtmidi_output:
                self.rtmidi_output.send_message([0x80, note, 0])
    
    def toggle_preview(self):
        if not self.midi_file:
            return
        
        if self.is_previewing:
            # Stop preview
            self.is_previewing = False
            self.preview_button.setText("Preview")
            self.stop_playing()
        else:
            # Start preview
            self.is_previewing = True
            self.preview_button.setText("Stop Preview")
            self.start_playing()
            self.statusBar().showMessage("Preview mode - listen to how the song should be played")
    
    def update_playback(self):
        # Poll for MIDI input if using pygame MIDI
        if isinstance(self.midi_input, pygame.midi.Input):
            if self.midi_input.poll():
                events = self.midi_input.read(10)  # Read up to 10
                for event in events:
                    data = event[0]
                    if data[0] & 0xF0 == 0x90:  # Note on
                        note = data[1]
                        velocity = data[2]
                        if velocity > 0:
                            self.handle_note_on(note, velocity)
                        else:
                            self.handle_note_off(note)
                    elif data[0] & 0xF0 == 0x80:  # Note off
                        note = data[1]
                        self.handle_note_off(note)
        
        if not self.is_playing or not self.midi_file:
            return
        
        elapsed = time.time() - self.current_time if not self.is_paused else self.pause_time - self.current_time
        self.note_canvas.update_playback_position(elapsed)
        
        # Track notes that should be currently playing
        currently_playing = set()
        
        # Find all notes that should be on at current time
        for i, event in enumerate(self.note_events):
            # Notes that started before or at current time
            if event['type'] == 'note_on' and event['time'] <= elapsed:
                note = event['note']
                
                # Find if this note has a corresponding note_off after current time
                is_still_playing = True
                for off_event in self.note_events[i:]:
                    if off_event['type'] == 'note_off' and off_event['note'] == note and off_event['time'] <= elapsed:
                        is_still_playing = False
                        break
                    if off_event['type'] == 'note_off' and off_event['note'] == note and off_event['time'] > elapsed:
                        break
                
                if is_still_playing:
                    currently_playing.add(note)
                    
                    # In preview mode, make sure the note is actually playing
                    if self.is_previewing and note not in self.playing_notes:
                        # Send to rtmidi_output directly
                        if self.rtmidi_output:
                            self.rtmidi_output.send_message([0x90, note, event['velocity']])
                        
                        # Update piano display
                        self.piano_display.note_on(note)
                        self.playing_notes.add(note)
        
        # Turn off notes that should no longer be playing
        if self.is_previewing:
            notes_to_turn_off = self.playing_notes - currently_playing
            for note in notes_to_turn_off:
                # Send to rtmidi_output directly
                if self.rtmidi_output:
                    self.rtmidi_output.send_message([0x80, note, 0])
                
                # Update piano display
                self.piano_display.note_off(note)
                self.playing_notes.remove(note)
        
        # Update expected notes for the user to play
        self.expected_notes = currently_playing
        
        # Check if playback is complete
        if elapsed > self.note_events[-1]['time'] + 2:
            self.stop_playing()
            if self.is_previewing:
                self.is_previewing = False
                self.preview_button.setText("Preview")
            self.statusBar().showMessage("Playback complete!")
    
    def update_score(self):
        if self.max_possible_score > 0:
            percentage = (self.score / self.max_possible_score) * 100
            self.score_label.setText(f"Score: {percentage:.1f}%")
    
    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Apply settings
            self.accuracy_threshold = dialog.get_accuracy_threshold()
            self.stream_speed = dialog.get_stream_speed()
            self.note_canvas.set_stream_speed(self.stream_speed)
    
    def show_about(self):
        QMessageBox.about(self, "About Piano Learning App",
                         "Piano Learning App\n\n"
                         "A MIDI-based tool to help learn piano songs.\n"
                         "Load a MIDI file, connect your MIDI keyboard, and practice!")
    
    def closeEvent(self, event):
        # Clean up MIDI resources
        if self.midi_input:
            if isinstance(self.midi_input, rtmidi.MidiIn):
                self.midi_input.close_port()
            else:
                self.midi_input.close()
        
        if self.midi_output:
            if isinstance(self.midi_output, rtmidi.MidiOut):
                self.midi_output.close_port()
            else:
                self.midi_output.close()
        
        if self.rtmidi_output:
            self.rtmidi_output.close_port()
        
        pygame.midi.quit()
        pygame.quit()
        
        event.accept()


# Helper function to get the tempo from a MIDI file
def get_tempo(midi_file):
    # Default tempo is 500,000 microseconds per beat (120 BPM)
    default_tempo = 500000

    for track in midi_file.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                return msg.tempo

    return default_tempo

# Settings dialog for configuring the application
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Settings")
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Accuracy threshold
        accuracy_layout = QHBoxLayout()
        accuracy_layout.addWidget(QLabel("Accuracy Threshold (%):"))
        self.accuracy_spinner = QSpinBox()
        self.accuracy_spinner.setRange(10, 100)
        self.accuracy_spinner.setValue(self.parent.accuracy_threshold)
        accuracy_layout.addWidget(self.accuracy_spinner)
        layout.addLayout(accuracy_layout)
        
        # Stream speed
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Stream Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(10, 200)
        self.speed_slider.setValue(self.parent.stream_speed)
        speed_layout.addWidget(self.speed_slider)
        self.speed_value = QLabel(f"{self.parent.stream_speed}")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_value.setText(str(v)))
        speed_layout.addWidget(self.speed_value)
        layout.addLayout(speed_layout)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_accuracy_threshold(self):
        return self.accuracy_spinner.value()
    
    def get_stream_speed(self):
        return self.speed_slider.value()

# Note Stream Canvas to display notes scrolling across the screen
class NoteStreamCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        
        # Configuration
        self.start_note = parent.start_note
        self.num_keys = parent.num_keys
        self.stream_speed = parent.stream_speed
        
        # State
        self.note_events = []
        self.current_position = 0
        
        # Set background color
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), Qt.GlobalColor.black)
        self.setPalette(palette)
    
    def set_note_events(self, events):
        self.note_events = events
        self.update()
    
    def set_stream_speed(self, speed):
        self.stream_speed = speed
        self.update()
    
    def update_playback_position(self, position):
        self.current_position = position
        self.update()
    
    def reset_playback(self):
        self.current_position = 0
        self.update()
    
    def paintEvent(self, event):
        if not self.note_events:
            return
        
        painter = QPainter(self)
        
        # Calculate dimensions
        width = self.width()
        height = self.height()
        key_width = width / self.num_keys
        
        # Draw grid lines for each key
        painter.setPen(Qt.GlobalColor.darkGray)
        for i in range(self.num_keys + 1):
            x = i * key_width
            painter.drawLine(int(x), 0, int(x), height)
        
        # Draw horizontal lines to indicate beats
        beat_height = 100  # pixels per beat
        beats = int(height / beat_height) + 1
        for i in range(beats):
            y = i * beat_height
            painter.drawLine(0, height - y, width, height - y)
        
        # Draw note events
        for event in self.note_events:
            if event['type'] == 'note_on':
                # Find matching note_off event
                note_off = None
                for off_event in self.note_events:
                    if (off_event['type'] == 'note_off' and 
                        off_event['note'] == event['note'] and 
                        off_event['time'] > event['time']):
                        note_off = off_event
                        break
                
                if note_off:
                    # Calculate position and size
                    note = event['note'] -self.start_note
                    if 0 <= note < self.num_keys:
                        x = note * key_width
                        
                        # Calculate y position based on time
                        start_y = height - (event['time'] - self.current_position) * self.stream_speed
                        end_y = height - (note_off['time'] - self.current_position) * self.stream_speed
                        
                        # Only draw if at least partially visible
                        if end_y > 0 and start_y < height:
                            # Adjust to visible area
                            if start_y > height:
                                start_y = height
                            if end_y < 0:
                                end_y = 0
                            
                            # Determine color based on whether it's a black key
                            is_black_key = (note % 12) in [1, 3, 6, 8, 10]
                            if is_black_key:
                                painter.setBrush(Qt.GlobalColor.darkCyan)
                            else:
                                painter.setBrush(Qt.GlobalColor.cyan)
                            
                            # Draw the note rectangle
                            painter.setPen(Qt.GlobalColor.black)
                            painter.drawRect(int(x), int(end_y), int(key_width), int(start_y - end_y))
        
        painter.end()

# Piano Keyboard Widget to display the piano keys and highlight pressed notes
class PianoKeyboardWidget(QWidget):
    def __init__(self, num_keys=48, start_note=36):
        super().__init__()
        
        self.num_keys = num_keys
        self.start_note = start_note
        self.pressed_keys = set()
        
        # Set minimum size
        self.setMinimumHeight(100)
    
    def note_on(self, note):
        if self.start_note <= note < self.start_note + self.num_keys:
            self.pressed_keys.add(note)
            self.update()
    
    def note_off(self, note):
        if note in self.pressed_keys:
            self.pressed_keys.remove(note)
            self.update()
    
    def reset(self):
        self.pressed_keys.clear()
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Calculate dimensions
        width = self.width()
        height = self.height()
        white_key_width = width / self.num_white_keys()
        
        # Draw white keys first
        painter.setPen(Qt.GlobalColor.black)
        for i in range(self.num_keys):
            note = self.start_note + i
            
            # Skip black keys for now
            if self.is_black_key(note):
                continue
            
            x = self.key_position(note) * white_key_width
            
            # Determine if key is pressed
            if note in self.pressed_keys:
                painter.setBrush(Qt.GlobalColor.lightGray)
            else:
                painter.setBrush(Qt.GlobalColor.white)
            
            painter.drawRect(int(x), 0, int(white_key_width), height)
        
        # Draw black keys on top
        black_key_width = white_key_width * 0.6
        black_key_height = height * 0.6
        
        for i in range(self.num_keys):
            note = self.start_note + i
            
            # Only draw black keys
            if not self.is_black_key(note):
                continue
            
            # Calculate position
            white_index = self.key_position(note)
            x = (white_index * white_key_width) - (black_key_width / 2)
            
            # Determine if key is pressed
            if note in self.pressed_keys:
                painter.setBrush(Qt.GlobalColor.darkGray)
            else:
                painter.setBrush(Qt.GlobalColor.black)
            
            painter.drawRect(int(x), 0, int(black_key_width), int(black_key_height))
        
        painter.end()
    
    def is_black_key(self, note):
        return (note % 12) in [1, 3, 6, 8, 10]
    
    def num_white_keys(self):
        count = 0
        for i in range(self.num_keys):
            if not self.is_black_key(self.start_note + i):
                count += 1
        return count
    
    def key_position(self, note):
        # Convert note to position among white keys
        position = 0
        for i in range(self.start_note, note):
            if not self.is_black_key(i):
                position += 1
        return position

# Main application entry point
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PianoLearningApp()
    window.show()
    sys.exit(app.exec())

