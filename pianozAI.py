import os
import sys
import time
import mido
import pygame
import pygame.midi
import rtmidi
import requests
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QPainter, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QGroupBox, QDialog, QDialogButtonBox, QSpinBox, QSlider, QLineEdit
)

class MidiPlayer(QThread):
    note_on = pyqtSignal(int, int)
    note_off = pyqtSignal(int)

    def __init__(self, note_events, rtmidi_output):
        super().__init__()
        self.note_events = note_events
        self.rtmidi_output = rtmidi_output
        self.is_playing = False

    def run(self):
        self.is_playing = True
        start_time = time.time()
        for event in self.note_events:
            if not self.is_playing:
                break
            elapsed = event['time'] - (time.time() - start_time)
            if elapsed > 0:
                time.sleep(elapsed)
            if event['type'] == 'note_on':
                if self.rtmidi_output:
                    self.rtmidi_output.send_message([0x90, event['note'], event['velocity']])
                self.note_on.emit(event['note'], event['velocity'])
            elif event['type'] == 'note_off':
                if self.rtmidi_output:
                    self.rtmidi_output.send_message([0x80, event['note'], 0])
                self.note_off.emit(event['note'])

    def stop(self):
        self.is_playing = False

class PianoLearningApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Piano Learning App")
        self.setGeometry(100, 100, 1200, 700)

        # Configuration
        self.midi_directory = "midi_songs"
        self.accuracy_threshold = 80
        self.num_keys = 48
        self.start_note = 36

        # MIDI variables
        self.midi_input = None
        self.midi_output = None
        self.midi_file = None
        self.midi_player = None
        self.playing_notes = set()
        self.expected_notes = set()
        self.note_events = []
        self.current_time = 0
        self.score = 0
        self.max_possible_score = 0
        self.stream_speed = 100
        self.is_playing = False
        self.is_paused = False
        self.is_previewing = False

        # Initialize pygame and pygame.midi
        pygame.init()
        pygame.midi.init()

        # Initialize rtmidi output
        self.rtmidi_output = None
        self.setup_rtmidi_output()

        # Load the UI
        self.init_ui()

        # Set up timer for GUI updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_gui)
        self.timer.start(50)  # Update every 50ms

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
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.create_menu_bar()

        self.note_canvas = NoteStreamCanvas(self)
        self.note_canvas.setMinimumHeight(300)
        main_layout.addWidget(self.note_canvas)

        self.piano_display = PianoKeyboardWidget(self.num_keys, self.start_note)
        self.piano_display.setMinimumHeight(120)
        main_layout.addWidget(self.piano_display)

        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        self.statusBar().showMessage("Ready")

        self.refresh_midi_devices()

    def create_menu_bar(self):
        menu_bar = self.menuBar()

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

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_control_panel(self):
        control_panel = QGroupBox("Controls")
        control_layout = QVBoxLayout(control_panel)

        input_device_layout = QHBoxLayout()
        input_device_layout.addWidget(QLabel("MIDI Input Device:"))
        self.midi_input_combo = QComboBox()
        self.midi_input_combo.currentIndexChanged.connect(self.select_midi_input)
        input_device_layout.addWidget(self.midi_input_combo)
        control_layout.addLayout(input_device_layout)

        output_device_layout = QHBoxLayout()
        output_device_layout.addWidget(QLabel("MIDI Output Device:"))
        self.midi_output_combo = QComboBox()
        self.midi_output_combo.currentIndexChanged.connect(self.select_midi_output)
        output_device_layout.addWidget(self.midi_output_combo)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_midi_devices)
        output_device_layout.addWidget(refresh_button)
        control_layout.addLayout(output_device_layout)

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

        self.generate_button = QPushButton("Generate Composition")
        self.generate_button.clicked.connect(self.generate_composition)
        playback_layout.addWidget(self.generate_button)

        control_layout.addLayout(playback_layout)

        # Dodajemy rozwijane listy stylów i kompozytorów
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("Style:"))
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "Etude", "Sonata", "Prelude", "Nocturne", "Waltz", "Mazurka",
            "Ballade", "Impromptu", "Scherzo", "Polonaise", "Fugue", "Rondo"
        ])
        style_layout.addWidget(self.style_combo)

        composer_layout = QHBoxLayout()
        composer_layout.addWidget(QLabel("Composer:"))
        self.composer_combo = QComboBox()
        self.composer_combo.addItems([
            "Bach", "Beethoven", "Chopin", "Mozart", "Liszt", "Schubert",
            "Tchaikovsky", "Debussy", "Rachmaninoff", "Scriabin", "Brahms", "Mendelssohn"
        ])
        composer_layout.addWidget(self.composer_combo)

        control_layout.addLayout(style_layout)
        control_layout.addLayout(composer_layout)

        info_layout = QHBoxLayout()
        self.song_label = QLabel("No song loaded")
        info_layout.addWidget(self.song_label)
        info_layout.addStretch(1)
        self.score_label = QLabel("Score: 0%")
        info_layout.addWidget(self.score_label)
        control_layout.addLayout(info_layout)

        return control_panel

    def refresh_midi_devices(self):
        current_input = self.midi_input_combo.currentText() if self.midi_input_combo.currentIndex() >= 0 else ""
        current_output = self.midi_output_combo.currentText() if self.midi_output_combo.currentIndex() >= 0 else ""

        self.midi_input_combo.clear()
        self.midi_output_combo.clear()

        self.midi_input_combo.addItem("None")
        self.midi_output_combo.addItem("None")

        try:
            midi_in = rtmidi.MidiIn()
            midi_out = rtmidi.MidiOut()
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

        try:
            for i in range(pygame.midi.get_count()):
                info = pygame.midi.get_device_info(i)
                name = info[1].decode('utf-8')
                is_input, is_output, is_opened = info[2], info[3], info[4]
                device_str = f"pygame: {name} (ID: {i})"
                if is_input and not is_opened:
                    self.midi_input_combo.addItem(device_str, ("pygame", i))
                if is_output and not is_opened:
                    self.midi_output_combo.addItem(device_str, ("pygame", i))
        except Exception as e:
            print(f"Error listing pygame MIDI devices: {e}")

        if current_input:
            index = self.midi_input_combo.findText(current_input)
            if index >= 0:
                self.midi_input_combo.setCurrentIndex(index)
        if current_output:
            index = self.midi_output_combo.findText(current_output)
            if index >= 0:
                self.midi_output_combo.setCurrentIndex(index)

        self.statusBar().showMessage(f"Found {self.midi_input_combo.count()-1} input and {self.midi_output_combo.count()-1} output MIDI devices")

    def select_midi_input(self, index):
        if index <= 0:
            if self.midi_input is not None:
                self.midi_input.close_port()
                self.midi_input = None
            return

        try:
            data = self.midi_input_combo.itemData(index)
            device_type, device_id = data
            device_name = self.midi_input_combo.currentText()

            if self.midi_input is not None:
                self.midi_input.close_port()
                self.midi_input = None

            if device_type == "rtmidi":
                self.midi_input = rtmidi.MidiIn()
                self.midi_input.open_port(device_id)
                def midi_callback(message, time_stamp):
                    data = message[0]
                    if data[0] & 0xF0 == 0x90:
                        note, velocity = data[1], data[2]
                        if velocity > 0:
                            self.handle_note_on(note, velocity)
                        else:
                            self.handle_note_off(note)
                    elif data[0] & 0xF0 == 0x80:
                        self.handle_note_off(data[1])
                self.midi_input.set_callback(midi_callback)
            elif device_type == "pygame":
                self.midi_input = pygame.midi.Input(device_id)

            self.statusBar().showMessage(f"Connected to MIDI input device: {device_name}")
        except Exception as e:
            self.statusBar().showMessage(f"Error connecting to MIDI input device: {e}")

    def select_midi_output(self, index):
        if index <= 0:
            if self.midi_output is not None:
                if isinstance(self.midi_output, rtmidi.MidiOut):
                    self.midi_output.close_port()
                else:
                    self.midi_output.close()
                self.midi_output = None
            return

        try:
            data = self.midi_output_combo.itemData(index)
            device_type, device_id = data
            device_name = self.midi_output_combo.currentText()

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

    def handle_note_on(self, note, velocity):
        self.piano_display.note_on(note)
        if self.midi_output:
            if isinstance(self.midi_output, rtmidi.MidiOut):
                self.midi_output.send_message([0x90, note, velocity])
            else:
                self.midi_output.note_on(note, velocity)
        if self.rtmidi_output:
            self.rtmidi_output.send_message([0x90, note, velocity])

        if self.is_playing and not self.is_previewing:
            if note in self.expected_notes:
                self.score += 1
                self.update_score()

        self.playing_notes.add(note)

    def handle_note_off(self, note):
        self.piano_display.note_off(note)
        if self.midi_output:
            if isinstance(self.midi_output, rtmidi.MidiOut):
                self.midi_output.send_message([0x80, note, 0])
            else:
                self.midi_output.note_off(note, 0)
        if self.rtmidi_output:
            self.rtmidi_output.send_message([0x80, note, 0])
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
            song_name = os.path.basename(file_path)
            self.song_label.setText(f"Song: {song_name}")
            self.process_midi_file()
            self.stop_playing()
            self.play_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.statusBar().showMessage(f"Loaded MIDI file: {song_name}")
        except Exception as e:
            self.statusBar().showMessage(f"Error loading MIDI file: {e}")

    def process_midi_file(self):
        if not self.midi_file:
            return

        self.note_events = []
        current_time = 0

        for track in self.midi_file.tracks:
            track_time = 0
            for msg in track:
                track_time += msg.time
                if msg.type == 'note_on' and msg.velocity > 0:
                    seconds = mido.tick2second(track_time, self.midi_file.ticks_per_beat, get_tempo(self.midi_file))
                    self.note_events.append({
                        'type': 'note_on',
                        'note': msg.note,
                        'velocity': msg.velocity,
                        'time': seconds
                    })
                elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                    seconds = mido.tick2second(track_time, self.midi_file.ticks_per_beat, get_tempo(self.midi_file))
                    self.note_events.append({
                        'type': 'note_off',
                        'note': msg.note,
                        'velocity': 0,
                        'time': seconds
                    })

        self.note_events = sorted(self.note_events, key=lambda x: x['time'])
        self.max_possible_score = len([e for e in self.note_events if e['type'] == 'note_on'])
        self.note_canvas.set_note_events(self.note_events)

    def start_playing(self):
        if not self.midi_file and not self.note_events:
            return

        if self.is_paused:
            self.is_paused = False
            self.current_time += time.time() - self.pause_time
        else:
            self.current_time = time.time()
            self.score = 0
            self.expected_notes = set()

        self.is_playing = True
        if self.is_previewing:
            self.midi_player = MidiPlayer(self.note_events, self.rtmidi_output)
            self.midi_player.note_on.connect(self.piano_display.note_on)
            self.midi_player.note_off.connect(self.piano_display.note_off)
            self.midi_player.start()

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
            if self.midi_player:
                self.midi_player.stop()

            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.statusBar().showMessage("Paused")

    def stop_playing(self):
        self.is_playing = False
        self.is_paused = False
        self.expected_notes = set()
        if self.midi_player:
            self.midi_player.stop()
            self.midi_player.wait()
            self.midi_player = None

        self.note_canvas.reset_playback()
        self.piano_display.reset()
        self.all_notes_off()

        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.preview_button.setEnabled(self.midi_file is not None or self.note_events)
        self.statusBar().showMessage("Stopped")

    def all_notes_off(self):
        for note in range(128):
            if self.midi_output:
                if isinstance(self.midi_output, rtmidi.MidiOut):
                    self.midi_output.send_message([0x80, note, 0])
                else:
                    self.midi_output.note_off(note, 0)
            if self.rtmidi_output:
                self.rtmidi_output.send_message([0x80, note, 0])

    def toggle_preview(self):
        if not self.midi_file and not self.note_events:
            return

        if self.is_previewing:
            self.is_previewing = False
            self.preview_button.setText("Preview")
            self.stop_playing()
        else:
            self.is_previewing = True
            self.preview_button.setText("Stop Preview")
            self.start_playing()
            self.statusBar().showMessage("Preview mode - listen to how the song should be played")

    def update_gui(self):
        if isinstance(self.midi_input, pygame.midi.Input):
            if self.midi_input.poll():
                events = self.midi_input.read(10)
                for event in events:
                    data = event[0]
                    if data[0] & 0xF0 == 0x90:
                        note, velocity = data[1], data[2]
                        if velocity > 0:
                            self.handle_note_on(note, velocity)
                        else:
                            self.handle_note_off(note)
                    elif data[0] & 0xF0 == 0x80:
                        self.handle_note_off(data[1])

        if not self.is_playing or (not self.midi_file and not self.note_events):
            return

        elapsed = time.time() - self.current_time if not self.is_paused else self.pause_time - self.current_time
        self.note_canvas.update_playback_position(elapsed)

        current_expected = set()
        window_start = elapsed - 0.5
        window_end = elapsed + 0.5

        for event in self.note_events:
            if event['time'] > window_end:
                break
            if window_start <= event['time'] <= window_end and event['type'] == 'note_on':
                current_expected.add(event['note'])

        self.expected_notes = current_expected

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

    def generate_composition(self):
        style = self.style_combo.currentText()
        composer = self.composer_combo.currentText()
        prompt = (
            f"Compose a short classical piano {style.lower()} in the style of {composer}. "
            "Return the notes and durations in this exact format: 'C4 0.5, D4 0.25, E4 1.0' "
            "(note space duration in seconds, separated by commas). Do not include any additional text."
        )
        composition = self.query_ollama_composer(prompt)

        if "Błąd" in composition:
            self.statusBar().showMessage(composition)
            return

        # Usuń kropkę lub inne znaki na końcu
        composition = composition.strip().rstrip(".")
        try:
            self.note_events = []
            current_time = 0
            for note_str in composition.split(","):
                note_str = note_str.strip()
                if not note_str:
                    continue
                note, duration = note_str.split()
                note_num = self.note_to_midi_number(note)
                duration_sec = float(duration)
                self.note_events.append({
                    "type": "note_on",
                    "note": note_num,
                    "velocity": 64,
                    "time": current_time
                })
                self.note_events.append({
                    "type": "note_off",
                    "note": note_num,
                    "velocity": 0,
                    "time": current_time + duration_sec
                })
                current_time += duration_sec

            self.note_events = sorted(self.note_events, key=lambda x: x["time"])
            self.max_possible_score = len([e for e in self.note_events if e["type"] == "note_on"])
            self.note_canvas.set_note_events(self.note_events)
            self.song_label.setText(f"Song: AI-Generated {style} by {composer}")
            self.midi_file = None  # Reset midi_file, bo to nowa kompozycja
            self.play_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.statusBar().showMessage(f"Generated {style} in the style of {composer}!")
        except Exception as e:
            self.statusBar().showMessage(f"Error parsing composition: {e}")

    def query_ollama_composer(self, prompt):
        url = "http://127.0.0.1:11434/api/generate"
        payload = {
            "model": "gemma3:1b",  # Zmień na "gemma3:1b" jeśli istnieje i chcesz użyć
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"Błąd: Serwer Ollama zwrócił kod {response.status_code}"
        except Exception as e:
            return f"Błąd: Nie można połączyć się z Ollama ({e})"

    def note_to_midi_number(self, note):
        """Konwertuje notację typu 'C4' na numer MIDI."""
        note_map = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
        note_name, octave = note[:-1], int(note[-1])
        return note_map[note_name] + (octave + 1) * 12  # MIDI: C4 = 60

    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.accuracy_threshold = dialog.get_accuracy_threshold()
            self.stream_speed = dialog.get_stream_speed()
            self.note_canvas.set_stream_speed(self.stream_speed)

    def show_about(self):
        QMessageBox.about(self, "About Piano Learning App",
                         "Piano Learning App\n\n"
                         "A MIDI-based tool to help learn piano songs.\n"
                         "Load a MIDI file, connect your MIDI keyboard, and practice!\n"
                         "Now with AI composition using Ollama!")

    def closeEvent(self, event):
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

def get_tempo(midi_file):
    default_tempo = 500000
    for track in midi_file.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                return msg.tempo
    return default_tempo

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Settings")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        accuracy_layout = QHBoxLayout()
        accuracy_layout.addWidget(QLabel("Accuracy Threshold (%):"))
        self.accuracy_spinner = QSpinBox()
        self.accuracy_spinner.setRange(50, 100)
        self.accuracy_spinner.setValue(self.parent.accuracy_threshold)
        accuracy_layout.addWidget(self.accuracy_spinner)
        layout.addLayout(accuracy_layout)

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Stream Speed:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(50, 200)
        self.speed_slider.setValue(self.parent.stream_speed)
        speed_layout.addWidget(self.speed_slider)
        self.speed_value = QLabel(f"{self.parent.stream_speed}")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_value.setText(str(v)))
        speed_layout.addWidget(self.speed_value)
        layout.addLayout(speed_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_accuracy_threshold(self):
        return self.accuracy_spinner.value()

    def get_stream_speed(self):
        return self.speed_slider.value()

class NoteStreamCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.start_note = parent.start_note
        self.num_keys = parent.num_keys
        self.stream_speed = parent.stream_speed
        self.note_events = []
        self.current_position = 0

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
        width = self.width()
        height = self.height()
        key_width = width / self.num_keys

        painter.setPen(Qt.GlobalColor.darkGray)
        for i in range(self.num_keys + 1):
            x = i * key_width
            painter.drawLine(int(x), 0, int(x), height)

        time_start = self.current_position - (height / self.stream_speed)
        time_end = self.current_position + (height / self.stream_speed)

        for event in self.note_events:
            if event['time'] > time_end:
                break
            if event['type'] == 'note_on' and event['time'] >= time_start:
                note_off = self.find_note_off(event)
                if note_off and note_off['time'] >= time_start:
                    note = event['note'] - self.start_note
                    if 0 <= note < self.num_keys:
                        x = note * key_width
                        start_y = height - (event['time'] - self.current_position) * self.stream_speed
                        end_y = height - (note_off['time'] - self.current_position) * self.stream_speed
                        if end_y > 0 and start_y < height:
                            start_y = max(0, start_y)
                            end_y = min(height, end_y)
                            is_black_key = (note % 12) in [1, 3, 6, 8, 10]
                            painter.setBrush(Qt.GlobalColor.darkCyan if is_black_key else Qt.GlobalColor.cyan)
                            painter.drawRect(int(x), int(end_y), int(key_width), int(start_y - end_y))

        painter.end()

    def find_note_off(self, note_on_event):
        for off_event in self.note_events:
            if (off_event['type'] == 'note_off' and
                off_event['note'] == note_on_event['note'] and
                off_event['time'] > note_on_event['time']):
                return off_event
        return None

class PianoKeyboardWidget(QWidget):
    def __init__(self, num_keys=48, start_note=36):
        super().__init__()
        self.num_keys = num_keys
        self.start_note = start_note
        self.pressed_keys = set()
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
        width = self.width()
        height = self.height()
        white_key_width = width / self.num_white_keys()

        painter.setPen(Qt.GlobalColor.black)
        for i in range(self.num_keys):
            note = self.start_note + i
            if self.is_black_key(note):
                continue
            x = self.key_position(note) * white_key_width
            painter.setBrush(Qt.GlobalColor.lightGray if note in self.pressed_keys else Qt.GlobalColor.white)
            painter.drawRect(int(x), 0, int(white_key_width), height)

        black_key_width = white_key_width * 0.6
        black_key_height = height * 0.6
        for i in range(self.num_keys):
            note = self.start_note + i
            if not self.is_black_key(note):
                continue
            white_index = self.key_position(note)
            x = (white_index * white_key_width) - (black_key_width / 2)
            painter.setBrush(Qt.GlobalColor.darkGray if note in self.pressed_keys else Qt.GlobalColor.black)
            painter.drawRect(int(x), 0, int(black_key_width), int(black_key_height))

        painter.end()

    def is_black_key(self, note):
        return (note % 12) in [1, 3, 6, 8, 10]

    def num_white_keys(self):
        return sum(1 for i in range(self.num_keys) if not self.is_black_key(self.start_note + i))

    def key_position(self, note):
        position = 0
        for i in range(self.start_note, note):
            if not self.is_black_key(i):
                position += 1
        return position

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PianoLearningApp()
    window.show()
    sys.exit(app.exec())
