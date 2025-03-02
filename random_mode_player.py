import time
import random
from PyQt6.QtCore import QTimer
from secrets import choice

# Struktury danych
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

class RandomModePlayer:
    def __init__(self, parent):
        self.parent = parent
        self.is_playing = False
        self.current_chord_notes = set()
        self.current_improv_notes = set()
        self.current_accomp_notes = set()
        self.timer = QTimer()
        self.timer.timeout.connect(self.play_next)
        self.seasons = ["Spring", "Summer", "Autumn", "Winter"]
        self.current_season = None
        self.current_hour = None
        self.base_octave = 36  # Początek w C2
        self.velocity = 80  # Głośność bazowa
        self.sequence_count = 0
        self.max_repeats = random.randint(2, 4)
        self.current_structure = None
        self.tempo_direction = random.choice(["increasing", "decreasing"])
        self.base_tempo = 1000
        self.current_scale_id = None
        self.partiture_start_time = 0
        self.partiture_duration = 0
        self.mode = "Mixed"  # Domyślny tryb: Mixed (Chords + Impro)

    def start_random_mode(self, mode="Mixed"):
        """Rozpoczyna odtwarzanie w wybranym trybie: Mixed, Only Impro, Only Chords."""
        if self.is_playing:
            self.stop()
        self.is_playing = True
        self.mode = mode  # Ustaw tryb: "Mixed", "Only Impro", "Only Chords"
        self.current_season = self.get_current_season()
        self.current_hour = self.get_current_hour()
        self.sequence_count = 0
        self.partiture_start_time = time.time()
        self.partiture_duration = random.uniform(60, 300)  # 1-5 minut
        self.current_scale_id = choice(list(SCALES.keys()))
        self.parent.statusBar().showMessage(
            f"Playing {mode} Mode - {self.current_season}, Hour: {self.current_hour}, Scale: {SCALES[self.current_scale_id]}"
        )
        self.play_next()
        self.timer.start(self.get_next_interval())

    def stop(self):
        self.is_playing = False
        self.timer.stop()
        self.all_notes_off()
        self.parent.statusBar().showMessage("Random Mode stopped")

    def get_current_season(self):
        month = int(time.strftime("%m"))
        if 3 <= month <= 5:
            return "Spring"
        elif 6 <= month <= 8:
            return "Summer"
        elif 9 <= month <= 11:
            return "Autumn"
        else:
            return "Winter"

    def get_current_hour(self):
        return int(time.strftime("%H"))

    def get_next_interval(self):
        base_tempo = self.base_tempo if self.mode == "Only Impro" else 2000  # Wolniejsze tempo dla akordów
        if self.current_season == "Spring":
            tempo_modifier = 0.9
        elif self.current_season == "Summer":
            tempo_modifier = 1.0
        elif self.current_season == "Autumn":
            tempo_modifier = 1.2
        else:  # Winter
            tempo_modifier = 1.5

        hour_modifier = 1.0
        if 6 <= self.current_hour < 12:
            hour_modifier = 0.8
        elif 12 <= self.current_hour < 18:
            hour_modifier = 1.0
        elif 18 <= self.current_hour < 22:
            hour_modifier = 1.2
        else:
            hour_modifier = 1.4

        tempo_change = (self.sequence_count / self.max_repeats) * 0.4
        if self.tempo_direction == "increasing":
            adjusted_tempo = base_tempo * (1 - tempo_change)
        else:
            adjusted_tempo = base_tempo * (1 + tempo_change)

        return int(adjusted_tempo * tempo_modifier * hour_modifier * random.uniform(0.8, 1.2))

    def generate_structure(self):
        structure_type = random.choice(["Chord", "Mode"])
        if structure_type == "Chord":
            chord_id = choice(BASIC_CHORDS)
            intervals = CHORDS_MIDI[chord_id]
            notes = self._get_notes_for_scale(self.current_scale_id, intervals)
            name = f"{SCALES[self.current_scale_id]}{CHORDS[chord_id]}"
        else:
            mode_id = choice(list(MODES.keys()))
            intervals = MODES_MIDI[mode_id]
            notes = self._get_notes_for_scale(self.current_scale_id, intervals)
            name = f"{SCALES[self.current_scale_id]} {MODES[mode_id]}"
        return {"type": structure_type, "name": name, "notes": notes}

    def _get_notes_for_scale(self, note_start, intervals):
        modified_notes = [note_start]
        for n in intervals:
            modified_notes.append(modified_notes[-1] + n)
        return modified_notes

    def generate_improvisation(self, base_notes):
        improv_notes = []
        num_notes = random.randint(3, 6)
        for _ in range(num_notes):
            base_note = random.choice(base_notes)
            improv_note = base_note + random.choice([-12, 0, 12, 24])
            improv_notes.append(improv_note)
        return improv_notes

    def generate_accompaniment(self, base_notes):
        accomp_notes = []
        root_note = base_notes[0] - 12
        accomp_notes.append(root_note)
        if random.choice([True, False]):
            accomp_notes.append(base_notes[1] - 12)
        return accomp_notes

    def play_next(self):
        if not self.is_playing or not self.parent.rtmidi_output:
            return

        # Sprawdź, czy partytura się zakończyła
        elapsed = time.time() - self.partiture_start_time
        if elapsed >= self.partiture_duration:
            self.current_scale_id = choice(list(SCALES.keys()))
            self.partiture_start_time = time.time()
            self.partiture_duration = random.uniform(60, 300)
            self.sequence_count = 0
            self.max_repeats = random.randint(2, 4)
            self.tempo_direction = random.choice(["increasing", "decreasing"])
            self.parent.statusBar().showMessage(
                f"New Partiture - {self.mode} Mode, Scale: {SCALES[self.current_scale_id]}, {self.current_season}, Hour: {self.current_hour}"
            )

        # Wyłącz poprzednie nuty
        self.all_notes_off()

        # Generuj nową strukturę, jeśli sekwencja się zakończyła
        if self.sequence_count == 0 or self.sequence_count >= self.max_repeats:
            self.current_structure = self.generate_structure()
            self.sequence_count = 0
            self.max_repeats = random.randint(2, 4)
            self.tempo_direction = random.choice(["increasing", "decreasing"])

        notes = self.current_structure["notes"]

        # Obsługa trybów
        if self.mode in ["Mixed", "Only Chords"]:
            # Subtelne akordy w tle
            octave_shift = random.choice([0, 12])
            adjusted_chord_notes = [note + self.base_octave + octave_shift for note in notes]
            self.current_chord_notes = set(adjusted_chord_notes)
            for note in self.current_chord_notes:
                self.parent.rtmidi_output.send_message([0x90, note, self.velocity - 40])  # Cichsze akordy
                self.parent.piano_display.note_on(note)

        if self.mode in ["Mixed", "Only Impro"]:
            # Improwizacja
            improv_notes = self.generate_improvisation(notes)
            adjusted_improv_notes = [note + self.base_octave + 24 for note in improv_notes]
            self.current_improv_notes = set(adjusted_improv_notes)
            improv_duration = random.uniform(0.3, 0.8)
            for i, note in enumerate(self.current_improv_notes):
                QTimer.singleShot(int(i * improv_duration * 1000), lambda n=note: self.play_improv_note(n))

        # Akompaniament tylko w trybie Mixed
        if self.mode == "Mixed":
            accomp_notes = self.generate_accompaniment(notes)
            self.current_accomp_notes = set([note + self.base_octave for note in accomp_notes])
            for note in self.current_accomp_notes:
                self.parent.rtmidi_output.send_message([0x90, note, self.velocity - 50])  # Bardzo cichy akompaniament
                self.parent.piano_display.note_on(note)

        # Zaktualizuj UI
        self.parent.question_label.setText(self.current_structure["name"])
        self.parent.answer_label.setText("")

        # Zwiększ licznik sekwencji
        self.sequence_count += 1

        # Ustaw czas trwania i zaplanuj następne zdarzenie
        duration = random.uniform(3.0, 6.0) if self.mode in ["Mixed", "Only Chords"] else random.uniform(1.5, 3.0)
        QTimer.singleShot(int(duration * 1000), self.all_notes_off)
        self.timer.setInterval(self.get_next_interval())

    def play_improv_note(self, note):
        if self.is_playing and self.parent.rtmidi_output:
            self.parent.rtmidi_output.send_message([0x90, note, self.velocity - 10])
            self.parent.piano_display.note_on(note)
            QTimer.singleShot(300, lambda: self.stop_improv_note(note))

    def stop_improv_note(self, note):
        if self.parent.rtmidi_output and note in self.current_improv_notes:
            self.parent.rtmidi_output.send_message([0x80, note, 0])
            self.parent.piano_display.note_off(note)

    def all_notes_off(self):
        if self.parent.rtmidi_output:
            for note in self.current_chord_notes | self.current_improv_notes | self.current_accomp_notes:
                self.parent.rtmidi_output.send_message([0x80, note, 0])
                self.parent.piano_display.note_off(note)
        self.current_chord_notes.clear()
        self.current_improv_notes.clear()
        self.current_accomp_notes.clear()
