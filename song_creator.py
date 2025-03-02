import sys
import time
import random
import mido
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QSpinBox, QListWidget, QListWidgetItem, QMessageBox, QFileDialog
)
from random_mode_player import RandomModePlayer, SCALES, CHORDS, CHORDS_MIDI, MODES, MODES_MIDI, BASIC_CHORDS

class SongCreator(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Song Creator")
        self.scale_id = 0
        self.key = "C"
        self.segments = []
        self.current_segment = None
        self.is_previewing = False
        self.preview_timer = QTimer()
        self.preview_timer.timeout.connect(self.update_preview)
        self.events = []
        self.random_player = RandomModePlayer(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Wybór skali i klucza
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(list(SCALES.values()))
        self.scale_combo.currentTextChanged.connect(self.update_scale)
        scale_layout.addWidget(self.scale_combo)
        layout.addLayout(scale_layout)

        # Lista segmentów
        self.segment_list = QListWidget()
        self.segment_list.itemClicked.connect(self.select_segment)
        layout.addWidget(QLabel("Song Segments:"))
        layout.addWidget(self.segment_list)

        # Dodawanie segmentu
        segment_layout = QVBoxLayout()
        
        type_layout = QHBoxLayout()
        self.segment_type_combo = QComboBox()
        self.segment_type_combo.addItems(["Intro", "Verse", "Chorus", "Outro"])
        type_layout.addWidget(QLabel("Segment Type:"))
        type_layout.addWidget(self.segment_type_combo)
        segment_layout.addLayout(type_layout)

        style_layout = QHBoxLayout()
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Repetitive", "Rising", "Falling", "Static", "Mixed"])
        style_layout.addWidget(QLabel("Style:"))
        style_layout.addWidget(self.style_combo)
        segment_layout.addLayout(style_layout)

        duration_layout = QHBoxLayout()
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 120)
        self.duration_spin.setValue(30)
        duration_layout.addWidget(QLabel("Duration (s):"))
        duration_layout.addWidget(self.duration_spin)
        segment_layout.addLayout(duration_layout)

        position_layout = QHBoxLayout()
        self.position_spin = QSpinBox()
        self.position_spin.setRange(0, 36)
        self.position_spin.setValue(random.randint(12, 24))
        position_layout.addWidget(QLabel("Start Position (semitones up):"))
        position_layout.addWidget(self.position_spin)
        segment_layout.addLayout(position_layout)

        add_button = QPushButton("Add Segment")
        add_button.clicked.connect(self.add_segment)
        segment_layout.addWidget(add_button)
        
        replace_button = QPushButton("Replace Segment")
        replace_button.clicked.connect(self.replace_segment)
        segment_layout.addWidget(replace_button)
        
        layout.addLayout(segment_layout)

        # Przyciski kontroli
        control_layout = QHBoxLayout()
        self.preview_segment_button = QPushButton("Preview Segment")
        self.preview_segment_button.clicked.connect(self.preview_segment)
        control_layout.addWidget(self.preview_segment_button)

        self.preview_song_button = QPushButton("Preview Song")
        self.preview_song_button.clicked.connect(self.preview_song)
        control_layout.addWidget(self.preview_song_button)

        self.export_button = QPushButton("Export to MIDI")
        self.export_button.clicked.connect(self.export_to_midi)
        control_layout.addWidget(self.export_button)
        layout.addLayout(control_layout)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def update_scale(self, scale):
        self.key = scale
        self.scale_id = [k for k, v in SCALES.items() if v == scale][0]
        self.status_label.setText(f"Scale updated to: {self.key}")

    def add_segment(self):
        segment = {
            "type": self.segment_type_combo.currentText(),
            "style": self.style_combo.currentText(),
            "duration": self.duration_spin.value(),
            "position": self.position_spin.value(),
            "notes": self.generate_segment_notes(
                self.scale_id, self.segment_type_combo.currentText(), self.style_combo.currentText(),
                self.duration_spin.value(), self.position_spin.value()
            )
        }
        self.segments.append(segment)
        item = QListWidgetItem(f"{segment['type']} - {segment['style']} ({segment['duration']}s, Pos: +{segment['position']})")
        self.segment_list.addItem(item)
        self.status_label.setText(f"Added {segment['type']} segment")
        self.position_spin.setValue(random.randint(12, 24))

    def replace_segment(self):
        selected = self.segment_list.currentRow()
        if selected < 0 or selected >= len(self.segments):
            QMessageBox.warning(self, "Error", "Select a segment to replace.")
            return
        segment = {
            "type": self.segment_type_combo.currentText(),
            "style": self.style_combo.currentText(),
            "duration": self.duration_spin.value(),
            "position": self.position_spin.value(),
            "notes": self.generate_segment_notes(
                self.scale_id, self.segment_type_combo.currentText(), self.style_combo.currentText(),
                self.duration_spin.value(), self.position_spin.value()
            )
        }
        self.segments[selected] = segment
        self.segment_list.item(selected).setText(f"{segment['type']} - {segment['style']} ({segment['duration']}s, Pos: +{segment['position']})")
        self.status_label.setText(f"Replaced segment {selected + 1}")
        self.position_spin.setValue(random.randint(12, 24))

    def generate_segment_notes(self, scale_id, segment_type, style, duration, position):
        notes = []
        base_octave = 36  # Bazowa oktawa C2, ale przesuwamy w sopranowy rejestr
        note_lengths = [0.5, 1.0, 2.0]  # Ćwierćnuta, półnuta, cała nuta

        self.random_player.current_scale_id = scale_id
        self.random_player.current_season = self.random_player.get_current_season()
        self.random_player.current_hour = self.random_player.get_current_hour()

        # Wybierz kilka unikalnych nut na cały segment
        structure = self.random_player.generate_structure()
        chord_notes = structure["notes"]
        available_notes = [note + base_octave + position for note in chord_notes]
        num_notes = min(3, len(available_notes))  # Maksymalnie 3 nuty w segmencie
        segment_notes = random.sample(available_notes, num_notes)

        # Rozmieść nuty w czasie zgodnie ze stylem
        time_pos = 0
        for i, note in enumerate(segment_notes):
            if time_pos >= duration:
                break
            note_duration = random.choice(note_lengths)

            if style == "Repetitive":
                # Jedna nuta rozłożona równomiernie w czasie
                time_pos = (duration / num_notes) * i
                if time_pos < duration:
                    notes.append({"type": "note_on", "note": note, "velocity": 60, "time": time_pos})
                    notes.append({"type": "note_off", "note": note, "velocity": 0, "time": time_pos + note_duration})

            elif style == "Rising":
                # Nuty wznoszą się w oktawach
                octave_shift = i * 12
                time_pos = (duration / num_notes) * i
                if time_pos < duration:
                    notes.append({"type": "note_on", "note": note + octave_shift, "velocity": 60, "time": time_pos})
                    notes.append({"type": "note_off", "note": note + octave_shift, "velocity": 0, "time": time_pos + note_duration})

            elif style == "Falling":
                # Nuty opadają w oktawach
                octave_shift = (num_notes - 1 - i) * 12
                time_pos = (duration / num_notes) * i
                if time_pos < duration:
                    notes.append({"type": "note_on", "note": note + octave_shift, "velocity": 60, "time": time_pos})
                    notes.append({"type": "note_off", "note": note + octave_shift, "velocity": 0, "time": time_pos + note_duration})

            elif style == "Static":
                # Nuty równomiernie rozłożone bez zmian oktawy
                time_pos = (duration / num_notes) * i
                if time_pos < duration:
                    notes.append({"type": "note_on", "note": note, "velocity": 60, "time": time_pos})
                    notes.append({"type": "note_off", "note": note, "velocity": 0, "time": time_pos + note_duration})

            elif style == "Mixed":
                # Losowy styl dla każdej nuty
                sub_style = random.choice(["Rising", "Falling", "Static"])
                time_pos = (duration / num_notes) * i
                if time_pos < duration:
                    octave_shift = i * 12 if sub_style == "Rising" else (num_notes - 1 - i) * 12 if sub_style == "Falling" else 0
                    notes.append({"type": "note_on", "note": note + octave_shift, "velocity": 60, "time": time_pos})
                    notes.append({"type": "note_off", "note": note + octave_shift, "velocity": 0, "time": time_pos + note_duration})

        return sorted(notes, key=lambda x: x["time"])

    def select_segment(self, item):
        index = self.segment_list.row(item)
        self.current_segment = self.segments[index]
        self.segment_type_combo.setCurrentText(self.current_segment["type"])
        self.style_combo.setCurrentText(self.current_segment["style"])
        self.duration_spin.setValue(self.current_segment["duration"])
        self.position_spin.setValue(self.current_segment["position"])
        self.status_label.setText(f"Selected: {self.current_segment['type']} - {self.current_segment['style']}")

    def preview_segment(self):
        if not self.current_segment:
            QMessageBox.warning(self, "Error", "Select a segment to preview.")
            return
        self.stop_preview()
        self.events = self.current_segment["notes"]
        self.start_preview()

    def preview_song(self):
        if not self.segments:
            QMessageBox.warning(self, "Error", "Add at least one segment to preview the song.")
            return
        self.stop_preview()
        self.events = []
        time_offset = 0
        for segment in self.segments:
            for event in segment["notes"]:
                self.events.append({
                    "type": event["type"],
                    "note": event["note"],
                    "velocity": event["velocity"],
                    "time": event["time"] + time_offset
                })
            time_offset += segment["duration"]
        self.start_preview()

    def start_preview(self):
        self.is_previewing = True
        self.preview_start_time = time.time()
        self.preview_timer.start(30)
        self.status_label.setText("Previewing...")

    def stop_preview(self):
        self.is_previewing = False
        self.preview_timer.stop()
        if self.parent.rtmidi_output:
            for note in range(128):
                self.parent.rtmidi_output.send_message([0x80, note, 0])
        self.parent.piano_display.reset()
        self.status_label.setText("Preview stopped")

    def update_preview(self):
        if not self.is_previewing or not self.parent.rtmidi_output:
            return
        elapsed = time.time() - self.preview_start_time
        currently_playing = set()

        for event in self.events:
            if event["time"] <= elapsed:
                if event["type"] == "note_on":
                    currently_playing.add(event["note"])
                    self.parent.rtmidi_output.send_message([0x90, event["note"], event["velocity"]])
                    self.parent.piano_display.note_on(event["note"])
                elif event["type"] == "note_off" and event["note"] in currently_playing:
                    currently_playing.remove(event["note"])
                    self.parent.rtmidi_output.send_message([0x80, event["note"], 0])
                    self.parent.piano_display.note_off(event["note"])

        if elapsed > self.events[-1]["time"]:
            self.stop_preview()

    def export_to_midi(self):
        if not self.segments:
            QMessageBox.warning(self, "Error", "No segments to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export to MIDI", "", "MIDI Files (*.mid)")
        if not file_path:
            return

        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage('set_tempo', tempo=500000, time=0))

        events = []
        time_offset = 0
        for segment in self.segments:
            for event in segment["notes"]:
                events.append({
                    "type": event["type"],
                    "note": event["note"],
                    "velocity": event["velocity"],
                    "time": event["time"] + time_offset
                })
            time_offset += segment["duration"]

        events = sorted(events, key=lambda x: x["time"])
        prev_time = 0
        for event in events:
            ticks = mido.second2tick(event["time"] - prev_time, mid.ticks_per_beat, 500000)
            prev_time = event["time"]
            if event["type"] == "note_on":
                track.append(mido.Message("note_on", note=event["note"], velocity=event["velocity"], time=int(ticks)))
            else:
                track.append(mido.Message("note_off", note=event["note"], velocity=0, time=int(ticks)))
        
        track.append(mido.MetaMessage('end_of_track', time=0))
        mid.save(file_path)
        self.status_label.setText(f"Song exported to {file_path}")

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    creator = SongCreator()
    creator.show()
    sys.exit(app.exec())
