import os
import sys
import time
import mido
import pygame
import pygame.midi
import rtmidi
from secrets import choice
from copy import deepcopy
import random
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QPainter, QColor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QFileDialog, QMessageBox,
    QGroupBox, QDialog, QDialogButtonBox, QSpinBox, QSlider, QLineEdit, QTextEdit
)
from random_mode_player import RandomModePlayer
from song_creator import SongCreator

# Struktury danych (pozostawione bez zmian)
SCALES = {
    0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F", 6: "Gb",
    7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B"
}

CHORDS = {
    0: "maj7", 1: "min7", 2: "min7/b5", 3: "7", 4: "dim", 5: "aug",
    6: "7/#11", 7: "maj7/#5", 8: "minM7", 9: "sus4/7", 10: "6", 11: "min6"
}

CHORDS_MIDI = {
    0: [4, 3, 4], 1: [3, 4, 3], 2: [3, 3, 4], 3: [4, 3, 3], 4: [3, 3, 3],
    5: [4, 4, 2], 6: [4, 2, 4], 7: [4, 4, 3], 8: [3, 4, 4], 9: [5, 2, 3],
    10: [4, 3, 2], 11: [3, 4, 2]
}

MODES = {
    0: "Ionian", 1: "Dorian", 2: "Phrygian", 3: "Lydian", 4: "Mixolydian",
    5: "Aeolian", 6: "Locrian"
}

MODES_MIDI = {
    0: [2, 2, 1, 2, 2, 2, 1], 1: [2, 1, 2, 2, 2, 1, 2], 2: [1, 2, 2, 2, 1, 2, 2],
    3: [2, 2, 2, 1, 2, 2, 1], 4: [2, 2, 1, 2, 2, 1, 2], 5: [2, 1, 2, 2, 1, 2, 2],
    6: [1, 2, 2, 1, 2, 2, 2]
}

BASIC_CHORDS = [0, 1, 3, 4, 5, 10, 11]

ENGLISH_ALPHABET_TO_NOTES = {
    'a': 60, 'b': 62, 'c': 64, 'd': 65, 'e': 67, 'f': 69, 'g': 71,
    'h': 72, 'i': 74, 'j': 76, 'k': 77, 'l': 79, 'm': 81, 'n': 83,
    'o': 84, 'p': 86, 'q': 88, 'r': 89, 's': 91, 't': 93, 'u': 95,
    'v': 96, 'w': 98, 'x': 100, 'y': 101, 'z': 103
}

POLISH_ALPHABET_TO_NOTES = {
    'a': 60, 'ą': 61, 'b': 62, 'c': 64, 'ć': 65, 'd': 66, 'e': 67,
    'ę': 68, 'f': 69, 'g': 71, 'h': 72, 'i': 74, 'j': 76, 'k': 77,
    'l': 79, 'ł': 80, 'm': 81, 'n': 83, 'ń': 84, 'o': 85, 'ó': 86,
    'p': 88, 'r': 89, 's': 91, 'ś': 92, 't': 93, 'u': 95, 'w': 96,
    'x': 98, 'y': 100, 'z': 101, 'ź': 102, 'ż': 103
}

TheoryItem = {
    "type": "", "name": "", "id": "", "desc": "", "scale": "", "notes": [],
    "scale_id": 0
}

class Theory:
    def __init__(self):
        pass

    def _get_common_items(self, type_: str) -> dict:
        item = deepcopy(TheoryItem)
        item["type"] = type_
        scale_id = choice(list(SCALES.keys()))
        item["scale_id"] = scale_id
        item["scale"] = SCALES[scale_id]
        return item

    def _get_notes_for_scale(self, note_start: int, intervals: list) -> list:
        modified_notes = [note_start]
        for n in intervals:
            modified_notes.append(modified_notes[-1] + n)
        return modified_notes

    def get_chord(self) -> dict:
        chord = self._get_common_items("Chord")
        chord_id = choice(BASIC_CHORDS)
        chord["id"] = chord_id
        chord["name"] = CHORDS[chord_id]
        chord["desc"] = CHORDS[chord_id]
        chord["notes"] = self._get_notes_for_scale(chord["scale_id"], CHORDS_MIDI[chord_id])
        return chord

    def get_mode(self) -> dict:
        mode = self._get_common_items("Mode")
        mode_id = choice(list(MODES.keys()))
        mode["id"] = mode_id
        mode["name"] = MODES[mode_id]
        mode["desc"] = MODES[mode_id]
        mode["notes"] = self._get_notes_for_scale(mode["scale_id"], MODES_MIDI[mode_id])
        return mode

class PianoLearningApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.theory = Theory()
        self.random_player = RandomModePlayer(self)
        self.theory_item = None
        self.good_notes = set()
        self.required_notes = []
        
        self.midi_directory = "midi_songs"
        self.accuracy_threshold = 80
        self.num_keys = 48
        self.start_note = 36
        
        self.midi_input = None
        self.midi_output = None
        self.midi_file = None
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
        self.pause_time = 0
        
        self.is_recording = False
        self.recording_start_time = 0
        self.recorded_events = []
        
        self.lyrics_notes = []
        self.lyrics_playback_time = 0
        
        pygame.init()
        pygame.midi.init()
        
        self.rtmidi_output = None
        self.setup_rtmidi_output()
        
        self.init_ui()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_playback)
        self.timer.start(30)

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
        
        song_creator_action = QAction("Song Creator", self)
        song_creator_action.triggered.connect(self.show_song_creator)
        file_menu.addAction(song_creator_action)
        
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

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Practice Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Song Mode", "Jazz Theory Mode", "Relaxation Mode", "Lyrics to Melody"])
        self.mode_combo.currentTextChanged.connect(self.switch_mode)
        mode_layout.addWidget(self.mode_combo)
        control_layout.addLayout(mode_layout)
    
        self.jazz_controls = QGroupBox("Jazz Theory")
        jazz_layout = QHBoxLayout(self.jazz_controls)
        self.jazz_type_combo = QComboBox()
        self.jazz_type_combo.addItems(["Chords", "Modes"])
        jazz_layout.addWidget(self.jazz_type_combo)
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.generate_theory_item)
        jazz_layout.addWidget(self.next_button)
        self.replay_button = QPushButton("Replay")
        self.replay_button.clicked.connect(self.replay_theory_item)
        jazz_layout.addWidget(self.replay_button)
        self.jazz_controls.setVisible(False)
        control_layout.addWidget(self.jazz_controls)

        self.relax_controls = QGroupBox("Relaxation Mode")
        relax_layout = QHBoxLayout(self.relax_controls)
        self.relax_mode_combo = QComboBox()
        self.relax_mode_combo.addItems(["Mixed (Chords + Impro)", "Only Impro", "Only Chords"])
        relax_layout.addWidget(QLabel("Submode:"))
        relax_layout.addWidget(self.relax_mode_combo)
        self.relax_controls.setVisible(False)
        control_layout.addWidget(self.relax_controls)

        self.lyrics_controls = QGroupBox("Lyrics to Melody")
        lyrics_layout = QVBoxLayout(self.lyrics_controls)
        lang_layout = QHBoxLayout()
        lang_layout.addWidget(QLabel("Language:"))
        self.lyrics_lang_combo = QComboBox()
        self.lyrics_lang_combo.addItems(["English", "Polish"])
        lang_layout.addWidget(self.lyrics_lang_combo)
        lyrics_layout.addLayout(lang_layout)
        
        self.load_lyrics_button = QPushButton("Load Lyrics File")
        self.load_lyrics_button.clicked.connect(self.load_lyrics_file)
        lyrics_layout.addWidget(self.load_lyrics_button)
        
        self.lyrics_preview_button = QPushButton("Preview Melody")
        self.lyrics_preview_button.clicked.connect(self.preview_lyrics_melody)
        lyrics_layout.addWidget(self.lyrics_preview_button)
        
        self.lyrics_text = QTextEdit()
        self.lyrics_text.setReadOnly(True)
        lyrics_layout.addWidget(self.lyrics_text)
        self.lyrics_controls.setVisible(False)
        control_layout.addWidget(self.lyrics_controls)

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
        
        self.record_button = QPushButton("Record Session")
        self.record_button.clicked.connect(self.toggle_recording)
        playback_layout.addWidget(self.record_button)
        control_layout.addLayout(playback_layout)
        
        info_layout = QHBoxLayout()
        self.song_label = QLabel("No song loaded")
        info_layout.addWidget(self.song_label)
        info_layout.addStretch(1)
        self.score_label = QLabel("Score: 0%")
        info_layout.addWidget(self.score_label)
        control_layout.addLayout(info_layout)
        
        self.question_label = QLabel("Press Next to Start")
        self.answer_label = QLabel("")
        control_layout.addWidget(self.question_label)
        control_layout.addWidget(self.answer_label)
        
        return control_panel

    def switch_mode(self, mode):
        self.all_notes_off()
        self.note_canvas.reset_playback()
        self.piano_display.reset()
        self.piano_display.set_expected_keys(set())
        
        if mode == "Song Mode":
            self.jazz_controls.setVisible(False)
            self.relax_controls.setVisible(False)
            self.lyrics_controls.setVisible(False)
            self.play_button.setVisible(True)
            self.pause_button.setVisible(True)
            self.stop_button.setVisible(True)
            self.preview_button.setVisible(True)
            self.record_button.setVisible(True)
            self.random_player.stop()
        elif mode == "Jazz Theory Mode":
            self.jazz_controls.setVisible(True)
            self.relax_controls.setVisible(False)
            self.lyrics_controls.setVisible(False)
            self.play_button.setVisible(False)
            self.pause_button.setVisible(False)
            self.stop_button.setVisible(False)
            self.preview_button.setVisible(False)
            self.record_button.setVisible(False)
            self.random_player.stop()
        elif mode == "Relaxation Mode":
            self.jazz_controls.setVisible(False)
            self.relax_controls.setVisible(True)
            self.lyrics_controls.setVisible(False)
            self.play_button.setVisible(False)
            self.pause_button.setVisible(False)
            self.stop_button.setVisible(False)
            self.preview_button.setVisible(False)
            self.record_button.setVisible(False)
            selected_mode = self.relax_mode_combo.currentText().split()[0]
            self.random_player.start_random_mode(selected_mode)
        elif mode == "Lyrics to Melody":
            self.jazz_controls.setVisible(False)
            self.relax_controls.setVisible(False)
            self.lyrics_controls.setVisible(True)
            self.play_button.setVisible(False)
            self.pause_button.setVisible(False)
            self.stop_button.setVisible(False)
            self.preview_button.setVisible(False)
            self.record_button.setVisible(False)
            self.random_player.stop()
            self.lyrics_notes = []

    def load_lyrics_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Lyrics", "", "Text Files (*.txt)")
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lyrics = f.read().strip().lower()
            if not lyrics:
                raise ValueError("File is empty or contains only whitespace")
            self.lyrics_text.setText(lyrics)
            self.generate_lyrics_melody(lyrics)
            self.statusBar().showMessage(f"Loaded lyrics from {os.path.basename(file_path)}")
            print(f"Loaded lyrics: {lyrics}")
            print(f"Generated notes: {self.lyrics_notes}")
        except Exception as e:
            self.statusBar().showMessage(f"Error loading lyrics: {e}")
            print(f"Error: {e}")

    def generate_lyrics_melody(self, lyrics):
        lang = self.lyrics_lang_combo.currentText()
        note_map = POLISH_ALPHABET_TO_NOTES if lang == "Polish" else ENGLISH_ALPHABET_TO_NOTES
        self.lyrics_notes = []
        time_pos = 0
        note_lengths = [0.5, 1.0, 2.0]  # ćwierćnuta, półnuta, cała nuta
        
        # Prosta analiza fonetyczna - podział na sylaby (przybliżona)
        def get_syllables(word):
            vowels = 'aeiouąęóy' if lang == "Polish" else 'aeiou'
            syllables = []
            current_syllable = ""
            for char in word:
                if char in vowels and current_syllable:
                    syllables.append(current_syllable)
                    current_syllable = char
                else:
                    current_syllable += char
            if current_syllable:
                syllables.append(current_syllable)
            return syllables

        words = lyrics.split()
        for word in words:
            if not word or word in ['ooo', 'oo']:  # Ignoruj "ooo" jako ozdobnik
                time_pos += 0.5
                continue
            
            syllables = get_syllables(word)
            for syl in syllables:
                first_char = syl[0]
                base_note = note_map.get(first_char, 60)
                syl_length = len(syl)
                note_duration = random.choice(note_lengths) * (1 + syl_length / 5)  # Dłuższe sylaby = dłuższe nuty
                
                self.lyrics_notes.append({"type": "note_on", "note": base_note, "velocity": 70, "time": time_pos})
                self.lyrics_notes.append({"type": "note_off", "note": base_note, "velocity": 0, "time": time_pos + note_duration})
                
                # Harmonia dla samogłosek
                vowels = 'aeiouąęóy' if lang == "Polish" else 'aeiou'
                vowel_count = sum(1 for char in syl if char in vowels)
                if vowel_count > 0 and random.random() < 0.3:  # 30% szans na harmonię
                    harmony_note = base_note + 4  # Tercja mała
                    harmony_duration = note_duration * 0.75
                    self.lyrics_notes.append({"type": "note_on", "note": harmony_note, "velocity": 60, "time": time_pos + note_duration * 0.25})
                    self.lyrics_notes.append({"type": "note_off", "note": harmony_note, "velocity": 0, "time": time_pos + note_duration * 0.25 + harmony_duration})
                
                time_pos += note_duration + random.uniform(0.1, 0.3)  # Krótsze przerwy dla płynności
        
        self.lyrics_notes = sorted(self.lyrics_notes, key=lambda x: x["time"])
        self.note_canvas.set_note_events(self.lyrics_notes)
        if not self.lyrics_notes:
            print("Warning: No notes generated!")

    def preview_lyrics_melody(self):
        if not self.lyrics_notes:
            QMessageBox.warning(self, "Error", "Load lyrics first.")
            print("self.lyrics_notes is empty!")
            return
        self.is_previewing = True
        self.lyrics_playback_time = time.time()
        self.statusBar().showMessage("Previewing Lyrics Melody...")
        print(f"Starting preview with {len(self.lyrics_notes)} notes")

    def update_playback(self):
        if isinstance(self.midi_input, pygame.midi.Input):
            if self.midi_input.poll():
                events = self.midi_input.read(10)
                for event in events:
                    data = event[0]
                    if data[0] & 0xF0 == 0x90:
                        note = data[1]
                        velocity = data[2]
                        if velocity > 0:
                            self.handle_note_on(note, velocity)
                        else:
                            self.handle_note_off(note)
                    elif data[0] & 0xF0 == 0x80:
                        note = data[1]
                        self.handle_note_off(note)
        
        current_mode = self.mode_combo.currentText()
        
        if current_mode == "Song Mode" and self.is_playing and self.midi_file:
            elapsed = time.time() - self.current_time if not self.is_paused else self.pause_time - self.current_time
            self.note_canvas.update_playback_position(elapsed)
            
            currently_playing = set()
            for i, event in enumerate(self.note_events):
                if event['type'] == 'note_on' and event['time'] <= elapsed:
                    note = event['note']
                    is_still_playing = True
                    for off_event in self.note_events[i:]:
                        if off_event['type'] == 'note_off' and off_event['note'] == note and off_event['time'] <= elapsed:
                            is_still_playing = False
                            break
                        if off_event['type'] == 'note_off' and off_event['note'] == note and off_event['time'] > elapsed:
                            break
                    if is_still_playing:
                        currently_playing.add(note)
                        if self.is_previewing and note not in self.playing_notes:
                            if self.rtmidi_output:
                                self.rtmidi_output.send_message([0x90, note, event['velocity']])
                            self.piano_display.note_on(note)
                            self.playing_notes.add(note)
            
            if self.is_previewing:
                notes_to_turn_off = self.playing_notes - currently_playing
                for note in notes_to_turn_off:
                    if self.rtmidi_output:
                        self.rtmidi_output.send_message([0x80, note, 0])
                    self.piano_display.note_off(note)
                    self.playing_notes.remove(note)
            
            self.expected_notes = currently_playing
            self.piano_display.set_expected_keys(self.expected_notes)
            
            if elapsed > self.note_events[-1]['time'] + 2:
                self.stop_playing()
                if self.is_previewing:
                    self.is_previewing = False
                    self.preview_button.setText("Preview")
                self.statusBar().showMessage("Playback complete!")
        
        elif current_mode == "Jazz Theory Mode":
            pass
        
        elif current_mode == "Relaxation Mode" and self.random_player.is_playing:
            pass
        
        elif current_mode == "Lyrics to Melody" and self.is_previewing and self.lyrics_notes:
            elapsed = time.time() - self.lyrics_playback_time
            self.note_canvas.update_playback_position(elapsed)
            currently_playing = set()
            
            for event in self.lyrics_notes:
                if event["time"] <= elapsed <= event["time"] + (event.get("duration", 0) or 0.5):  # Sprawdź czas trwania
                    if event["type"] == "note_on" and event["note"] not in currently_playing:
                        currently_playing.add(event["note"])
                        if self.rtmidi_output:
                            self.rtmidi_output.send_message([0x90, event["note"], event["velocity"]])
                            print(f"Playing note_on: {event['note']} at {event['time']}")
                        self.piano_display.note_on(event["note"])
                    elif event["type"] == "note_off" and event["note"] in currently_playing:
                        currently_playing.remove(event["note"])
                        if self.rtmidi_output:
                            self.rtmidi_output.send_message([0x80, event["note"], 0])
                            print(f"Playing note_off: {event['note']} at {event['time']}")
                        self.piano_display.note_off(event["note"])
            
            self.playing_notes = currently_playing
            if elapsed > self.lyrics_notes[-1]["time"] + 0.5:  # Dodatkowy bufor
                self.is_previewing = False
                self.all_notes_off()
                self.statusBar().showMessage("Lyrics Melody preview complete")
                print("Preview finished")

    def show_song_creator(self):
        creator = SongCreator(self)
        creator.exec()

    def generate_theory_item(self):
        if self.mode_combo.currentText() != "Jazz Theory Mode":
            return
        
        if self.jazz_type_combo.currentText() == "Chords":
            self.theory_item = self.theory.get_chord()
        else:
            self.theory_item = self.theory.get_mode()
        
        self.good_notes = set([n + i for i in [36, 48, 60, 72] for n in self.theory_item["notes"]])
        self.required_notes = [[n + 36, n + 48, n + 60, n + 72] for n in self.theory_item["notes"]]
        
        q = f"{SCALES[self.theory_item['scale_id']]}"
        if self.theory_item["type"] == "Chord":
            q += self.theory_item["name"]
            answer_text = q
        else:
            answer_text = f"{q} {self.theory_item['name']}"
        self.question_label.setText(q)
        self.answer_label.setText("")
        
        self.piano_display.set_expected_keys(self.good_notes)
        
        if self.rtmidi_output:
            for note in self.theory_item["notes"]:
                self.rtmidi_output.send_message([0x90, note + 36, 100])
            time.sleep(1)
            for note in self.theory_item["notes"]:
                self.rtmidi_output.send_message([0x80, note + 36, 0])
        
        self.timer.singleShot(10000, lambda: self.reveal_answer(answer_text))

    def replay_theory_item(self):
        if not self.theory_item or self.mode_combo.currentText() != "Jazz Theory Mode":
            return
        if self.rtmidi_output:
            self.piano_display.set_expected_keys(self.good_notes)
            for note in self.theory_item["notes"]:
                self.rtmidi_output.send_message([0x90, note + 36, 100])
            time.sleep(1)
            for note in self.theory_item["notes"]:
                self.rtmidi_output.send_message([0x80, note + 36, 0])

    def reveal_answer(self, answer_text):
        if self.theory_item and self.mode_combo.currentText() == "Jazz Theory Mode":
            self.answer_label.setText(answer_text)

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
        
        if current_input:
            index = self.midi_input_combo.findText(current_input)
            if index >= 0:
                self.midi_input_combo.setCurrentIndex(index)
        
        if current_output:
            index = self.midi_output_combo.findText(current_output)
            if index >= 0:
                self.midi_output_combo.setCurrentIndex(index)
        
        if self.midi_input_combo.count() > 1 or self.midi_output_combo.count() > 1:
            self.statusBar().showMessage(f"Found {self.midi_input_combo.count()-1} input and {self.midi_output_combo.count()-1} output MIDI devices")
        else:
            self.statusBar().showMessage("No MIDI devices found. Try connecting a MIDI keyboard and click Refresh.")

    def select_midi_input(self, index):
        if index <= 0:
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
            
            if self.midi_input is not None:
                self.midi_input.close_port()
                self.midi_input = None
            
            if device_type == "rtmidi":
                self.midi_input = rtmidi.MidiIn()
                self.midi_input.open_port(device_id)
                
                def midi_callback(message, time_stamp):
                    data = message[0]
                    if data[0] & 0xF0 == 0x90:
                        note = data[1]
                        velocity = data[2]
                        if velocity > 0:
                            self.handle_note_on(note, velocity)
                        else:
                            self.handle_note_off(note)
                    elif data[0] & 0xF0 == 0x80:
                        note = data[1]
                        self.handle_note_off(note)
                
                self.midi_input.set_callback(midi_callback)
            
            elif device_type == "pygame":
                self.midi_input = pygame.midi.Input(device_id)
            
            self.statusBar().showMessage(f"Connected to MIDI input device: {device_name}")
            
        except Exception as e:
            self.statusBar().showMessage(f"Error connecting to MIDI input device: {e}")
            if self.midi_input is not None:
                self.midi_input.close_port()
                self.midi_input = None

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
            if not data:
                return
                
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
            if self.midi_output is not None:
                if isinstance(self.midi_output, rtmidi.MidiOut):
                    self.midi_output.close_port()
                else:
                    self.midi_output.close()
                self.midi_output = None

    def handle_note_on(self, note, velocity):
        self.piano_display.note_on(note)
        
        if self.midi_output:
            if isinstance(self.midi_output, rtmidi.MidiOut):
                self.midi_output.send_message([0x90, note, velocity])
            else:
                self.midi_output.note_on(note, velocity)
        
        if self.rtmidi_output:
            self.rtmidi_output.send_message([0x90, note, velocity])
        
        if self.is_recording:
            elapsed = time.time() - self.recording_start_time
            self.recorded_events.append({
                'type': 'note_on', 'note': note, 'velocity': velocity, 'time': elapsed
            })
        
        self.playing_notes.add(note)
        
        if self.mode_combo.currentText() == "Jazz Theory Mode" and self.theory_item:
            if note in self.good_notes:
                ids_to_remove = []
                for i, req_set in enumerate(self.required_notes):
                    if note in req_set:
                        ids_to_remove.append(i)
                for i in sorted(ids_to_remove, reverse=True):
                    del self.required_notes[i]
                if not self.required_notes:
                    self.timer.stop()
                    self.reveal_answer(self.answer_label.text() or f"{SCALES[self.theory_item['scale_id']]}{self.theory_item['name']}")
                    self.piano_display.set_expected_keys(set())
                self.statusBar().showMessage(f"Correct note: {note}")
            else:
                self.statusBar().showMessage(f"Wrong note: {note}")
        
        elif self.is_playing and not self.is_previewing:
            if note in self.expected_notes:
                self.score += 1
                self.update_score()

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
            elapsed = time.time() - self.recording_start_time
            self.recorded_events.append({
                'type': 'note_off',
                'note': note,
                'velocity': 0,
                'time': elapsed
            })
        
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
        tempo = get_tempo(self.midi_file)
        active_notes = {}
        
        for track in self.midi_file.tracks:
            track_time = 0
            for msg in track:
                track_time += msg.time
                seconds = mido.tick2second(track_time, self.midi_file.ticks_per_beat, tempo)
                
                if msg.type == 'note_on' and hasattr(msg, 'velocity'):
                    note = msg.note
                    if msg.velocity > 0:
                        self.note_events.append({
                            'type': 'note_on',
                            'note': note,
                            'velocity': msg.velocity,
                            'time': seconds
                        })
                        active_notes[note] = seconds
                    else:
                        self.note_events.append({
                            'type': 'note_off',
                            'note': note,
                            'velocity': 0,
                            'time': seconds
                        })
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
                    if note in active_notes:
                        del active_notes[note]
                elif msg.type == 'set_tempo':
                    tempo = msg.tempo
        
        for note, start_time in active_notes.items():
            self.note_events.append({
                'type': 'note_off',
                'note': note,
                'velocity': 0,
                'time': start_time + 2
            })
        
        self.note_events = sorted(self.note_events, key=lambda x: x['time'])
        self.max_possible_score = len([e for e in self.note_events if e['type'] == 'note_on'])
        self.note_canvas.set_note_events(self.note_events)

    def start_playing(self):
        if not self.midi_file:
            return
        
        if self.is_paused:
            self.is_paused = False
            self.current_time += time.time() - self.pause_time
        else:
            self.current_time = time.time()
            self.score = 0
            self.expected_notes = set()
        
        self.is_playing = True
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
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.statusBar().showMessage("Paused")

    def stop_playing(self):
        self.is_playing = False
        self.is_paused = False
        self.expected_notes = set()
        self.note_canvas.reset_playback()
        self.piano_display.reset()
        self.all_notes_off()
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.preview_button.setEnabled(self.midi_file is not None)
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
        if not self.midi_file:
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

    def toggle_recording(self):
        if self.is_recording:
            self.is_recording = False
            self.record_button.setText("Record Session")
            if self.recorded_events:
                self.save_recording_to_midi()
            self.statusBar().showMessage("Recording stopped")
        else:
            self.is_recording = True
            self.record_button.setText("Stop Recording")
            self.recorded_events = []
            self.recording_start_time = time.time()
            self.statusBar().showMessage("Recording started")

    def save_recording_to_midi(self):
        if not self.recorded_events:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Recording", self.midi_directory, "MIDI Files (*.mid)"
        )
        
        if not file_path:
            return
        
        try:
            mid = mido.MidiFile()
            track = mido.MidiTrack()
            mid.tracks.append(track)
            tempo = 500000
            track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
            sorted_events = sorted(self.recorded_events, key=lambda x: x['time'])
            prev_time = 0
            for event in sorted_events:
                current_ticks = mido.second2tick(event['time'], mid.ticks_per_beat, tempo)
                delta_ticks = current_ticks - prev_time
                prev_time = current_ticks
                if event['type'] == 'note_on':
                    msg = mido.Message('note_on', note=event['note'], velocity=event['velocity'], time=int(delta_ticks))
                else:
                    msg = mido.Message('note_off', note=event['note'], velocity=0, time=int(delta_ticks))
                track.append(msg)
            track.append(mido.MetaMessage('end_of_track', time=0))
            mid.save(file_path)
            self.statusBar().showMessage(f"Recording saved to: {os.path.basename(file_path)}")
        except Exception as e:
            self.statusBar().showMessage(f"Error saving recording: {e}")

    def update_score(self):
        if self.max_possible_score > 0:
            percentage = (self.score / self.max_possible_score) * 100
            self.score_label.setText(f"Score: {percentage:.1f}%")

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
                         "Load a MIDI file, connect your MIDI keyboard, and practice!")

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

# Helper function to get the tempo from a MIDI file
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
        self.accuracy_spinner.setRange(10, 100)
        self.accuracy_spinner.setValue(self.parent.accuracy_threshold)
        accuracy_layout.addWidget(self.accuracy_spinner)
        layout.addLayout(accuracy_layout)
        
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
        
        beat_height = 100
        beats = int(height / beat_height) + 1
        for i in range(beats):
            y = i * beat_height
            painter.drawLine(0, height - y, width, height - y)
        
        for event in self.note_events:
            if event['type'] == 'note_on':
                note_off = None
                for off_event in self.note_events:
                    if (off_event['type'] == 'note_off' and 
                        off_event['note'] == event['note'] and 
                        off_event['time'] > event['time']):
                        note_off = off_event
                        break
                
                if note_off:
                    note = event['note'] - self.start_note
                    if 0 <= note < self.num_keys:
                        x = note * key_width
                        start_y = height - (event['time'] - self.current_position) * self.stream_speed
                        end_y = height - (note_off['time'] - self.current_position) * self.stream_speed
                        
                        if end_y > 0 and start_y < height:
                            if start_y > height:
                                start_y = height
                            if end_y < 0:
                                end_y = 0
                            
                            is_black_key = (note % 12) in [1, 3, 6, 8, 10]
                            if is_black_key:
                                painter.setBrush(Qt.GlobalColor.darkCyan)
                            else:
                                painter.setBrush(Qt.GlobalColor.cyan)
                            painter.setPen(Qt.GlobalColor.black)
                            painter.drawRect(int(x), int(end_y), int(key_width), int(start_y - end_y))
        
        painter.end()

class PianoKeyboardWidget(QWidget):
    def __init__(self, num_keys=48, start_note=36):
        super().__init__()
        self.num_keys = num_keys
        self.start_note = start_note
        self.pressed_keys = set()
        self.expected_keys = set()
        self.setMinimumHeight(100)
    
    def set_expected_keys(self, keys):
        self.expected_keys = keys
        self.update()
    
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
        self.expected_keys.clear()
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
            if note in self.pressed_keys:
                painter.setBrush(Qt.GlobalColor.lightGray)
            elif note in self.expected_keys:
                painter.setBrush(Qt.GlobalColor.yellow)
            else:
                painter.setBrush(Qt.GlobalColor.white)
            painter.drawRect(int(x), 0, int(white_key_width), height)
        
        black_key_width = white_key_width * 0.6
        black_key_height = height * 0.6
        for i in range(self.num_keys):
            note = self.start_note + i
            if not self.is_black_key(note):
                continue
            white_index = self.key_position(note)
            x = (white_index * white_key_width) - (black_key_width / 2)
            if note in self.pressed_keys:
                painter.setBrush(Qt.GlobalColor.darkGray)
            elif note in self.expected_keys:
                painter.setBrush(QColor(255, 255, 150))
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
