import os
import sys
import time
import mido
import pygame
import pygame.midi
import rtmidi
import requests
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QPainter, QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QGroupBox, QSpinBox, QSlider, QListWidget, QAbstractItemView
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

class MidiRecorder:
    def __init__(self):
        self.events = []
        self.start_time = None

    def start(self):
        self.events = []
        self.start_time = time.time()

    def record_note_on(self, note, velocity):
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.events.append({'type': 'note_on', 'note': note, 'velocity': velocity, 'time': elapsed})

    def record_note_off(self, note):
        if self.start_time is not None:
            elapsed = time.time() - self.start_time
            self.events.append({'type': 'note_off', 'note': note, 'velocity': 0, 'time': elapsed})

    def stop(self):
        self.start_time = None

    def save(self, filepath):
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        last_time = 0
        for event in sorted(self.events, key=lambda x: x['time']):
            delta_time = int((event['time'] - last_time) * 1000)
            last_time = event['time']
            if event['type'] == 'note_on':
                track.append(mido.Message('note_on', note=event['note'], velocity=event['velocity'], time=delta_time))
            elif event['type'] == 'note_off':
                track.append(mido.Message('note_off', note=event['note'], velocity=0, time=delta_time))
        mid.save(filepath)

class PianoLearningApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Piano Learning App")
        self.setGeometry(100, 100, 1200, 700)

        # Configuration
        self.midi_directory = "songs_midi"
        self.rec_directory = "recs_midi"
        os.makedirs(self.midi_directory, exist_ok=True)
        os.makedirs(self.rec_directory, exist_ok=True)
        self.accuracy_threshold = 80
        self.num_keys = 48
        self.start_note = 36
        self.stream_speed = 100

        # MIDI variables
        self.midi_input = None
        self.midi_output = None
        self.midi_file = None
        self.midi_player = None
        self.recorder = MidiRecorder()
        self.playing_notes = set()
        self.expected_notes = set()
        self.note_events = []
        self.current_time = 0
        self.score = 0
        self.max_possible_score = 0
        self.is_playing = False
        self.is_paused = False
        self.is_previewing = False
        self.is_recording = False

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
        self.timer.start(50)

        # Load last settings
        self.load_settings()

    def setup_rtmidi_output(self):
        try:
            self.rtmidi_output = rtmidi.MidiOut()
            available_ports = self.rtmidi_output.get_ports()
            if available_ports:
                self.rtmidi_output.open_port(0)
            else:
                self.rtmidi_output.open_virtual_port("PianoLearningApp Output")
        except Exception as e:
            print("Error opening rtmidi output:", e)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.create_menu_bar()

        # Song selector nad NoteStreamCanvas
        song_selector_panel = self.create_song_selector_panel()
        main_layout.addWidget(song_selector_panel)

        self.note_canvas = NoteStreamCanvas(self)
        self.note_canvas.setMinimumHeight(300)
        main_layout.addWidget(self.note_canvas)

        self.piano_display = PianoKeyboardWidget(self.num_keys, self.start_note)
        self.piano_display.setMinimumHeight(120)
        main_layout.addWidget(self.piano_display)

        settings_panel = self.create_settings_panel()
        main_layout.addWidget(settings_panel)

        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        midi_io_panel = self.create_midi_io_panel()
        main_layout.addWidget(midi_io_panel)

        self.statusBar().showMessage("Ready")

        self.refresh_midi_devices()

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        save_action = QAction("Save Generated MIDI", self)
        save_action.triggered.connect(self.save_generated_midi)
        file_menu.addAction(save_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_song_selector_panel(self):
        song_selector_panel = QGroupBox("Song Selector")
        song_selector_layout = QHBoxLayout(song_selector_panel)

        self.song_list = QListWidget()
        self.song_list.setStyleSheet("""
            QListWidget {
                background-color: #FF4500;
                color: #00FF7F;
                font-family: "Courier New";
                font-size: 14px;
                border: 2px solid #00FF7F;
            }
            QListWidget::item:selected {
                background-color: #00FF7F;
                color: #FF4500;
            }
        """)
        self.song_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.song_list.itemSelectionChanged.connect(self.load_selected_song)
        self.load_song_list()
        song_selector_layout.addWidget(self.song_list)

        load_button = QPushButton("Load File")
        load_button.clicked.connect(self.load_midi_file_from_dialog)
        song_selector_layout.addWidget(load_button)

        clear_button = QPushButton("Clear List")
        clear_button.clicked.connect(self.clear_song_list)
        song_selector_layout.addWidget(clear_button)

        return song_selector_panel

    def create_settings_panel(self):
        settings_panel = QGroupBox("Settings")
        settings_layout = QHBoxLayout(settings_panel)

        accuracy_layout = QHBoxLayout()
        accuracy_layout.addWidget(QLabel("Accuracy Threshold (%):"))
        self.accuracy_spinner = QSpinBox()
        self.accuracy_spinner.setRange(50, 100)
        self.accuracy_spinner.setValue(self.accuracy_threshold)
        accuracy_layout.addWidget(self.accuracy_spinner)
        settings_layout.addLayout(accuracy_layout)

        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Tempo:"))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 200)
        self.speed_slider.setSingleStep(1)
        self.speed_slider.setValue(self.stream_speed)
        self.speed_slider.valueChanged.connect(self.update_tempo)
        speed_layout.addWidget(self.speed_slider)
        self.speed_value = QLabel(f"{self.stream_speed}")
        self.speed_slider.valueChanged.connect(lambda v: self.speed_value.setText(str(v)))
        speed_layout.addWidget(self.speed_value)
        settings_layout.addLayout(speed_layout)

        return settings_panel

    def create_control_panel(self):
        control_panel = QGroupBox("Controls")
        control_layout = QHBoxLayout(control_panel)

        self.play_button = QPushButton()
        self.play_button.setIcon(QIcon.fromTheme("media-playback-start"))
        self.play_button.clicked.connect(self.start_playing)
        control_layout.addWidget(self.play_button)

        self.pause_button = QPushButton()
        self.pause_button.setIcon(QIcon.fromTheme("media-playback-pause"))
        self.pause_button.clicked.connect(self.pause_playing)
        self.pause_button.setEnabled(False)
        control_layout.addWidget(self.pause_button)

        self.stop_button = QPushButton()
        self.stop_button.setIcon(QIcon.fromTheme("media-playback-stop"))
        self.stop_button.clicked.connect(self.stop_playing)
        self.stop_button.setEnabled(False)
        control_layout.addWidget(self.stop_button)

        self.preview_button = QPushButton()
        self.preview_button.setIcon(QIcon.fromTheme("media-seek-forward"))
        self.preview_button.clicked.connect(self.toggle_preview)
        control_layout.addWidget(self.preview_button)

        self.record_button = QPushButton()
        self.record_button.setIcon(QIcon.fromTheme("media-record"))
        self.record_button.clicked.connect(self.toggle_recording)
        control_layout.addWidget(self.record_button)

        generate_layout = QHBoxLayout()
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Arp", "Chords", "Bassline", "Lead", "Pad", "Pluck", "Drum Pattern", "Synth Stab", "Ambient Texture", "Breakbeat"])
        generate_layout.addWidget(self.style_combo)

        self.artist_combo = QComboBox()
        self.artist_combo.addItems(["Deadmau5", "Skrillex", "Aphex Twin", "Daft Punk", "Calvin Harris", "The Chainsmokers", "Justice", "Disclosure", "Four Tet", "Bonobo"])
        generate_layout.addWidget(self.artist_combo)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems(["10", "20", "30", "40", "50", "60", "70", "80", "90", "100"])
        generate_layout.addWidget(self.duration_combo)

        self.generate_button = QPushButton()
        self.generate_button.setIcon(QIcon.fromTheme("document-new"))
        self.generate_button.clicked.connect(self.generate_composition)
        generate_layout.addWidget(self.generate_button)

        control_layout.addLayout(generate_layout)

        self.song_label = QLabel("No song loaded")
        control_layout.addWidget(self.song_label)
        control_layout.addStretch(1)
        self.score_label = QLabel("Score: 0%")
        control_layout.addWidget(self.score_label)

        return control_panel

    def create_midi_io_panel(self):
        midi_io_panel = QGroupBox("MIDI I/O")
        midi_io_layout = QHBoxLayout(midi_io_panel)

        midi_io_layout.addWidget(QLabel("Input:"))
        self.midi_input_combo = QComboBox()
        self.midi_input_combo.currentIndexChanged.connect(self.select_midi_input)
        midi_io_layout.addWidget(self.midi_input_combo)

        midi_io_layout.addWidget(QLabel("Output:"))
        self.midi_output_combo = QComboBox()
        self.midi_output_combo.currentIndexChanged.connect(self.select_midi_output)
        midi_io_layout.addWidget(self.midi_output_combo)

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_midi_devices)
        midi_io_layout.addWidget(refresh_button)

        return midi_io_panel

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
            self.save_settings()
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
            self.save_settings()
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

        if self.is_recording:
            self.recorder.record_note_on(note, velocity)

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

        if self.is_recording:
            self.recorder.record_note_off(note)

        if note in self.playing_notes:
            self.playing_notes.remove(note)

    def load_midi_file(self, file_path):
        try:
            self.midi_file = mido.MidiFile(file_path)
            song_name = os.path.basename(file_path)
            self.song_label.setText(f"Song: {song_name}")
            self.process_midi_file()
            self.stop_playing()
            self.play_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            tempo = mido.tempo2bpm(get_tempo(self.midi_file))
            self.speed_slider.setValue(int(tempo))
            self.speed_value.setText(str(int(tempo)))
            self.stream_speed = int(tempo)
            self.note_canvas.set_stream_speed(self.stream_speed)
            self.statusBar().showMessage(f"Loaded MIDI file: {song_name}")
        except Exception as e:
            self.statusBar().showMessage(f"Error loading MIDI file: {e}")

    def load_midi_file_from_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load MIDI File", self.midi_directory, "MIDI Files (*.mid *.midi)")
        if file_path:
            self.load_midi_file(file_path)
            self.load_song_list()  # Odśwież listę po załadowaniu nowego pliku

    def load_selected_song(self):
        selected = self.song_list.currentItem()
        if selected:
            text = selected.text()
            if text.startswith("[REC] "):
                file_path = os.path.join(self.rec_directory, text[6:])
            else:
                file_path = os.path.join(self.midi_directory, text)
            self.load_midi_file(file_path)

    def load_song_list(self):
        self.song_list.clear()
        for file in os.listdir(self.midi_directory):
            if file.endswith((".mid", ".midi")):
                self.song_list.addItem(file)
        for file in os.listdir(self.rec_directory):
            if file.endswith((".mid", ".midi")):
                self.song_list.addItem(f"[REC] {file}")

    def clear_song_list(self):
        self.song_list.clear()

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
        self.preview_button.setEnabled(self.midi_file is not None or len(self.note_events) > 0)
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
            self.preview_button.setIcon(QIcon.fromTheme("media-seek-forward"))
            self.stop_playing()
        else:
            self.is_previewing = True
            self.preview_button.setIcon(QIcon.fromTheme("media-stop"))
            self.start_playing()
            self.statusBar().showMessage("Preview mode - listen to how the song should be played")

    def toggle_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.recorder.stop()
            self.record_button.setIcon(QIcon.fromTheme("media-record"))
            file_path, _ = QFileDialog.getSaveFileName(self, "Save Recording", self.rec_directory, "MIDI Files (*.mid)")
            if file_path:
                self.recorder.save(file_path)
                self.load_song_list()  # Odśwież listę po zapisaniu nagrania
                self.statusBar().showMessage(f"Recording saved to {file_path}")
        else:
            self.is_recording = True
            self.recorder.start()
            self.record_button.setIcon(QIcon.fromTheme("media-stop"))
            self.statusBar().showMessage("Recording...")

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

        self.stream_speed = self.speed_slider.value()
        self.note_canvas.set_stream_speed(self.stream_speed)

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
        self.piano_display.set_expected_notes(self.expected_notes)

        if elapsed > self.note_events[-1]['time'] + 2:
            self.stop_playing()
            if self.is_previewing:
                self.is_previewing = False
                self.preview_button.setIcon(QIcon.fromTheme("media-seek-forward"))
            self.statusBar().showMessage("Playback complete!")

    def update_tempo(self, value):
        self.stream_speed = value
        self.note_canvas.set_stream_speed(value)

    def update_score(self):
        if self.max_possible_score > 0:
            percentage = (self.score / self.max_possible_score) * 100
            self.score_label.setText(f"Score: {percentage:.1f}%")

    def generate_composition(self):
        style = self.style_combo.currentText()
        artist = self.artist_combo.currentText()
        duration_seconds = int(self.duration_combo.currentText())
        prompt = (
            f"Compose an electronic music {style.lower()} in the style of {artist} "
            f"with a duration of approximately {duration_seconds} second{'s' if duration_seconds != 1 else ''}. "
            "Return the notes and durations in this exact format: 'C4 0.5, D4 0.25, E4 1.0' "
            "(note space duration in seconds, separated by commas). Do not include any additional text."
        )
        composition = self.query_ollama_composer(prompt)

        if "Błąd" in composition:
            self.statusBar().showMessage(composition)
            return

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
            self.song_label.setText(f"Song: AI-Generated {style} by {artist} ({duration_seconds}s)")
            self.midi_file = None
            self.play_button.setEnabled(True)
            self.preview_button.setEnabled(True)
            self.statusBar().showMessage(f"Generated {style} in the style of {artist} lasting {duration_seconds} second{'s' if duration_seconds != 1 else ''}!")
        except Exception as e:
            self.statusBar().showMessage(f"Error parsing composition: {e}")

    def query_ollama_composer(self, prompt):
        url = "http://127.0.0.1:11434/api/generate"
        payload = {
            "model": "gemma3:27b",
            "prompt": prompt,
            "stream": False
        }
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                return response.json()["response"]
            else:
                return f"Błąd: Serwer Ollama zwrócił kod {response.status_code}"
        except requests.exceptions.ConnectionError:
            return "Błąd: Nie można połączyć się z serwerem Ollama. Upewnij się, że 'ollama serve' działa."
        except Exception as e:
            return f"Błąd: Wystąpił problem z zapytaniem do Ollama ({e})"

    def note_to_midi_number(self, note):
        note_map = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
        note_name, octave = note[:-1], int(note[-1])
        return note_map[note_name] + (octave + 1) * 12

    def save_generated_midi(self):
        if not self.note_events:
            self.statusBar().showMessage("No composition to save!")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Generated MIDI", self.midi_directory, "MIDI Files (*.mid)")
        if file_path:
            mid = mido.MidiFile()
            track = mido.MidiTrack()
            mid.tracks.append(track)
            last_time = 0
            for event in sorted(self.note_events, key=lambda x: x['time']):
                delta_time = int((event['time'] - last_time) * 1000)
                last_time = event['time']
                if event['type'] == 'note_on':
                    track.append(mido.Message('note_on', note=event['note'], velocity=event['velocity'], time=delta_time))
                elif event['type'] == 'note_off':
                    track.append(mido.Message('note_off', note=event['note'], velocity=0, time=delta_time))
            mid.save(file_path)
            self.load_song_list()  # Odśwież listę po zapisaniu
            self.statusBar().showMessage(f"Generated MIDI saved to {file_path}")

    def show_about(self):
        QMessageBox.about(self, "About Piano Learning App",
                         "Piano Learning App\n\n"
                         "A MIDI-based tool to help learn piano songs.\n"
                         "Load a MIDI file, connect your MIDI keyboard, and practice!\n"
                         "Now with AI composition, recording, and saving using Ollama!")

    def save_settings(self):
        with open("settings.txt", "w") as f:
            f.write(f"input:{self.midi_input_combo.currentText()}\n")
            f.write(f"output:{self.midi_output_combo.currentText()}\n")
            f.write(f"threshold:{self.accuracy_spinner.value()}\n")
            f.write(f"tempo:{self.speed_slider.value()}\n")

    def load_settings(self):
        try:
            with open("settings.txt", "r") as f:
                settings = dict(line.strip().split(":", 1) for line in f)
            self.accuracy_spinner.setValue(int(settings.get("threshold", 80)))
            self.speed_slider.setValue(int(settings.get("tempo", 100)))
            self.speed_value.setText(settings.get("tempo", "100"))
            self.stream_speed = int(settings.get("tempo", 100))
            input_device = settings.get("input", "")
            output_device = settings.get("output", "")
            if input_device:
                index = self.midi_input_combo.findText(input_device)
                if index >= 0:
                    self.midi_input_combo.setCurrentIndex(index)
                    self.select_midi_input(index)
            if output_device:
                index = self.midi_output_combo.findText(output_device)
                if index >= 0:
                    self.midi_output_combo.setCurrentIndex(index)
                    self.select_midi_output(index)
        except FileNotFoundError:
            pass

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
        self.save_settings()
        event.accept()

def get_tempo(midi_file):
    default_tempo = 500000  # ~120 BPM
    for track in midi_file.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                return msg.tempo
    return default_tempo

class NoteStreamCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.start_note = parent.start_note
        self.num_keys = parent.num_keys
        self.stream_speed = parent.stream_speed
        self.note_events = []
        self.current_position = 0
        self.pulse_phase = 0

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
        self.pulse_phase = (self.pulse_phase + 1) % 20
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
        note_order = {}

        order = 1
        seen_times = {}
        for event in self.note_events:
            if event['time'] > time_end:
                break
            if (event['type'] == 'note_on' and
                event['time'] >= self.current_position and
                event['time'] not in seen_times):
                note_order[event['note']] = order
                seen_times[event['time']] = True
                order += 1

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

                            if event['time'] <= self.current_position + 0.5:
                                alpha = 255 - int((self.pulse_phase / 20) * 100)
                                color = QColor(0, 255, 255, alpha) if not is_black_key else QColor(0, 139, 139, alpha)
                            else:
                                color = Qt.GlobalColor.cyan if not is_black_key else Qt.GlobalColor.darkCyan

                            painter.setBrush(color)
                            painter.drawRect(int(x), int(end_y), int(key_width), int(start_y - end_y))

                            if event['note'] in note_order and event['time'] >= self.current_position:
                                painter.setPen(QColor(255, 255, 0))
                                painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
                                num_x = x + key_width / 2 - 7
                                num_y = start_y - 10
                                painter.drawText(int(num_x), int(num_y), str(note_order[event['note']]))

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
        self.expected_notes = set()
        self.setMinimumHeight(100)

    def note_on(self, note):
        if self.start_note <= note < self.start_note + self.num_keys:
            self.pressed_keys.add(note)
            self.update()

    def note_off(self, note):
        if note in self.pressed_keys:
            self.pressed_keys.remove(note)
            self.update()

    def set_expected_notes(self, notes):
        self.expected_notes = notes
        self.update()

    def reset(self):
        self.pressed_keys.clear()
        self.expected_notes.clear()
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

            if note in self.expected_notes:
                painter.setPen(Qt.GlobalColor.red)
                painter.setFont(QFont("Arial", 8))
                note_name = self.midi_to_note_name(note)
                painter.drawText(int(x + white_key_width / 2 - 10), int(height - 10), note_name)

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

            if note in self.expected_notes:
                painter.setPen(Qt.GlobalColor.red)
                painter.setFont(QFont("Arial", 8))
                note_name = self.midi_to_note_name(note)
                painter.drawText(int(x + black_key_width / 2 - 10), int(black_key_height - 10), note_name)

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

    def midi_to_note_name(self, midi_note):
        note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
        octave = (midi_note // 12) - 1
        note_index = midi_note % 12
        return f"{note_names[note_index]}{octave}"

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PianoLearningApp()
    window.show()
    sys.exit(app.exec())
