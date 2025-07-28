import pytest
from unittest.mock import Mock, MagicMock, patch # נשתמש ב-patch לדימוי יבואים חיצוניים
from pathlib import Path
from typing import Any

# ייבוא המחלקות שנבדקות
from EventSystem import Publisher, Observer
from GameObservers import ScoreDisplay, MoveListDisplay, SoundPlayer
from img import Img # נשתמש ב-Img המקורי עבור ה-Mock של הקנבס


# ──────────────────────────────────────────────────────────────────────────
#                                 Shared Fixtures
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_game_instance():
    """Returns a mock Game instance with necessary attributes for observers."""
    game = Mock()
    game.game_time_ms.return_value = 1000 # מדמה זמן כלשהו
    game.canvas_width = 1280
    game.canvas_height = 720
    return game

@pytest.fixture
def mock_canvas():
    """Returns a mock Img object to simulate the drawing canvas."""
    canvas = Mock(spec=Img) # Mock an Img object
    canvas.put_text = Mock() # Mock the put_text method specifically
    return canvas

# ──────────────────────────────────────────────────────────────────────────
#                                 ScoreDisplay Tests
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def score_display(mock_game_instance):
    player1_pos = (10, 10)
    player2_pos = (100, 10)
    return ScoreDisplay(mock_game_instance, player1_pos, player2_pos)

def test_score_display_init(score_display):
    """Sanity: ScoreDisplay initializes with zero scores."""
    # Assert
    assert score_display.scores == {'W': 0, 'B': 0}

def test_score_display_update_piece_captured_white_pawn(score_display):
    """Sanity: Score updates correctly for white capturing black pawn."""
    # Arrange
    event_type = "piece_captured"
    kwargs = {'captured_piece_type': 'P', 'captured_by_player_side': 'W'}

    # Act
    score_display.update(event_type, **kwargs)

    # Assert
    assert score_display.scores == {'W': 1, 'B': 0}

def test_score_display_update_piece_captured_black_queen(score_display):
    """Sanity: Score updates correctly for black capturing white queen."""
    # Arrange
    event_type = "piece_captured"
    kwargs = {'captured_piece_type': 'Q', 'captured_by_player_side': 'B'}

    # Act
    score_display.update(event_type, **kwargs)

    # Assert
    assert score_display.scores == {'W': 0, 'B': 9}


def test_score_display_update_multiple_captures(score_display):
    """Sanity: Score accumulates correctly over multiple captures."""
    # Arrange
    score_display.update("piece_captured", captured_piece_type='P', captured_by_player_side='W') # W captures pawn
    score_display.update("piece_captured", captured_piece_type='N', captured_by_player_side='B') # B captures knight

    # Act
    score_display.update("piece_captured", captured_piece_type='R', captured_by_player_side='W') # W captures rook
    score_display.update("piece_captured", captured_piece_type='B', captured_by_player_side='B') # B captures bishop

    # Assert
    assert score_display.scores == {'W': 1 + 5, 'B': 3 + 3} # W: 6, B: 6


def test_score_display_update_game_start(score_display):
    """Sanity: Score resets to zero on game_start event."""
    # Arrange
    score_display.scores = {'W': 10, 'B': 5} # Set some initial score
    event_type = "game_start"

    # Act
    score_display.update(event_type)

    # Assert
    assert score_display.scores == {'W': 0, 'B': 0}


def test_score_display_update_game_end(score_display):
    """Sanity: Score does not change on game_end event, but logs."""
    # Arrange
    score_display.scores = {'W': 10, 'B': 5}
    event_type = "game_end"
    
    with patch('logging.Logger.info') as mock_log_info: # Mock logging.info
        # Act
        score_display.update(event_type)

        # Assert
        assert score_display.scores == {'W': 10, 'B': 5} # Score should not change
        mock_log_info.assert_called_with("Game ended. Final Score: White: 10, Black: 5")


def test_score_display_draw(score_display, mock_canvas):
    """Sanity: draw calls put_text with correct score strings and positions."""
    # Arrange
    score_display.scores = {'W': 7, 'B': 12}

    # Act
    score_display.draw(mock_canvas)

    # Assert
    mock_canvas.put_text.assert_any_call(f"P1 Score: 7", 10, 10, Any, color=(0, 255, 0, 255), thickness=Any)
    mock_canvas.put_text.assert_any_call(f"P2 Score: 12", 100, 10, Any, color=(255, 0, 0, 255), thickness=Any)
    assert mock_canvas.put_text.call_count == 2 # Verify exactly two calls


# ──────────────────────────────────────────────────────────────────────────
#                                MoveListDisplay Tests
# ──────────────────────────────────────────────────────────────────────────

@pytest.fixture
def move_list_display():
    player1_pos = (10, 50)
    player2_pos = (100, 50)
    return MoveListDisplay(player1_pos, player2_pos, max_moves_to_show=2)

def test_move_list_display_init(move_list_display):
    """Sanity: MoveListDisplay initializes with empty move lists."""
    # Assert
    assert move_list_display.player1_moves == []
    assert move_list_display.player2_moves == []

def test_move_list_display_update_player1_move(move_list_display):
    """Sanity: Player 1 move is added correctly."""
    # Arrange
    kwargs = {'piece_id': 'PW_1', 'from_cell': (6, 4), 'to_cell': (4, 4), 'player': 1}

    # Act
    move_list_display.update("move", **kwargs)

    # Assert
    assert move_list_display.player1_moves == ["P e2->e4"]
    assert move_list_display.player2_moves == []


def test_move_list_display_update_player2_jump(move_list_display):
    """Sanity: Player 2 jump to new cell is added correctly."""
    # Arrange
    kwargs = {'piece_id': 'NB_1', 'from_cell': (0, 1), 'to_cell': (2, 2), 'player': 2}

    # Act
    move_list_display.update("jump", **kwargs)

    # Assert
    assert move_list_display.player1_moves == []
    assert move_list_display.player2_moves == ["N b8->c6"]

def test_move_list_display_update_player1_jump_in_place(move_list_display):
    """Sanity: Player 1 jump in place is formatted correctly."""
    # Arrange
    kwargs = {'piece_id': 'KW_1', 'from_cell': (7, 4), 'to_cell': (7, 4), 'player': 1}

    # Act
    move_list_display.update("jump", **kwargs)

    # Assert
    assert move_list_display.player1_moves == ["P1 K jumped in place"]
    assert move_list_display.player2_moves == []

def test_move_list_display_update_max_moves_to_show(move_list_display):
    """Edge case: Move list respects max_moves_to_show."""
    # Arrange
    move_list_display.max_moves_to_show = 1 # Set max to 1
    move_list_display.update("move", piece_id='PW_1', from_cell=(6, 0), to_cell=(5, 0), player=1) # First move

    # Act
    move_list_display.update("move", piece_id='PW_2', from_cell=(6, 1), to_cell=(5, 1), player=1) # Second move

    # Assert
    assert len(move_list_display.player1_moves) == 1
    assert move_list_display.player1_moves == ["P b2->b3"] # Only the last move should remain


def test_move_list_display_update_game_start(move_list_display):
    """Sanity: Move list clears on game_start event."""
    # Arrange
    move_list_display.player1_moves.append("P e2->e4")
    move_list_display.player2_moves.append("P d7->d5")
    
    # Act
    move_list_display.update("game_start")

    # Assert
    assert move_list_display.player1_moves == []
    assert move_list_display.player2_moves == []


def test_move_list_display_draw(move_list_display, mock_canvas):
    """Sanity: draw calls put_text for all moves in correct positions."""
    # Arrange
    move_list_display.player1_moves = ["P e2->e4", "N b1->c3"]
    move_list_display.player2_moves = ["P d7->d5"]

    # Act
    move_list_display.draw(mock_canvas)

    # Assert
    mock_canvas.put_text.assert_any_call("P e2->e4", 10, 50, Any, color=Any, thickness=Any)
    mock_canvas.put_text.assert_any_call("N b1->c3", 10, 50 + 18, Any, color=Any, thickness=Any) # Next line
    mock_canvas.put_text.assert_any_call("P d7->d5", 100, 50, Any, color=Any, thickness=Any)
    assert mock_canvas.put_text.call_count == 3


# ──────────────────────────────────────────────────────────────────────────
#                                 SoundPlayer Tests
# ──────────────────────────────────────────────────────────────────────────

# Mock pygame.mixer.Sound for testing
class MockSound:
    def __init__(self, path: str):
        self.path = path
        self.play_called = False
        self.num_plays = 0
        self.play_args = []
        self.play_kwargs = {}

    def play(self, loops=0, maxtime=0, fade_ms=0):
        self.play_called = True
        self.num_plays += 1
        self.play_args.append((loops, maxtime, fade_ms))

# Mock pygame.mixer object for testing
class MockMixer:
    def __init__(self):
        self.Sound = Mock(side_effect=MockSound) # Sound() will return MockSound objects
        self.init = Mock()
        self.quit = Mock()

@pytest.fixture
def mock_mixer():
    """Fixture to provide a mocked pygame.mixer."""
    return MockMixer()

@pytest.fixture
def sound_player_instance(tmp_path, mock_mixer):
    """Fixture for SoundPlayer with mocked sounds directory and mixer."""
    # Arrange: Create dummy sound files in a temporary directory
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()
    (sounds_dir / "foot_step_1.mp3").write_text("dummy sound data")
    (sounds_dir / "jump.wav").write_text("dummy sound data")
    (sounds_dir / "gun.wav").write_text("dummy sound data")
    (sounds_dir / "TADA.WAV").write_text("dummy sound data")
    (sounds_dir / "applause.mp3").write_text("dummy sound data")
    (sounds_dir / "gamestart.mp3").write_text("dummy sound data")

    # Patch the global mixer import in GameObservers to use our mock
    with patch('GameObservers.mixer', new=mock_mixer):
        sp = SoundPlayer(sounds_dir)
        return sp

def test_sound_player_load_sounds_sanity(sound_player_instance, mock_mixer):
    """Sanity: SoundPlayer loads all expected sounds successfully."""
    # Assert
    assert len(sound_player_instance.sounds) == 6 # Should try to load all 6 types
    for sound_type in ["move", "jump", "piece_captured", "pawn_promoted", "game_end", "game_start"]:
        assert isinstance(sound_player_instance.sounds[sound_type], MockSound)
        assert mock_mixer.Sound.call_args_list # mixer.Sound should have been called for loading


def test_sound_player_load_sounds_missing_file(tmp_path, mock_mixer):
    """Edge case: SoundPlayer handles missing sound files gracefully."""
    # Arrange: Create sounds directory but no files inside
    sounds_dir = tmp_path / "sounds"
    sounds_dir.mkdir()

    with patch('GameObservers.mixer', new=mock_mixer):
        sp = SoundPlayer(sounds_dir) # Act: Initialize SoundPlayer with empty dir

        # Assert: No sound objects should be loaded for any type
        for sound_type in sp.sounds:
            assert sp.sounds[sound_type] is None


def test_sound_player_update_move_event(sound_player_instance):
    """Sanity: 'move' event triggers sound playback with maxtime."""
    # Arrange
    mock_move_sound = sound_player_instance.sounds["move"] # Get the mocked sound object

    # Act
    sound_player_instance.update("move")

    # Assert
    assert mock_move_sound.play_called
    assert mock_move_sound.num_plays == 1
    # Verify maxtime parameter was passed (loops=0, maxtime=200)
    assert mock_move_sound.play_args[0] == (0, 200) 


def test_sound_player_update_capture_event(sound_player_instance):
    """Sanity: 'piece_captured' event triggers sound playback."""
    # Arrange
    mock_capture_sound = sound_player_instance.sounds["piece_captured"]

    # Act
    sound_player_instance.update("piece_captured")

    # Assert
    assert mock_capture_sound.play_called
    assert mock_capture_sound.num_plays == 1
    assert mock_capture_sound.play_args[0] == (0, 0) # No maxtime


def test_sound_player_update_game_end_event(sound_player_instance):
    """Sanity: 'game_end' event triggers sound playback."""
    # Arrange
    mock_game_end_sound = sound_player_instance.sounds["game_end"]

    # Act
    sound_player_instance.update("game_end")

    # Assert
    assert mock_game_end_sound.play_called
    assert mock_game_end_sound.num_plays == 1


def test_sound_player_update_unhandled_event(sound_player_instance):
    """Edge case: Unhandled event types do not trigger sound playback."""
    # Arrange
    # Reset play_called flags for all sounds
    for sound_type in sound_player_instance.sounds:
        if sound_player_instance.sounds[sound_type]:
            sound_player_instance.sounds[sound_type].play_called = False

    # Act
    sound_player_instance.update("some_other_event")

    # Assert
    # No sound should have been played
    for sound_type in sound_player_instance.sounds:
        if sound_player_instance.sounds[sound_type]:
            assert not sound_player_instance.sounds[sound_type].play_called


@patch('GameObservers.mixer', new_callable=Mock) # Patch mixer at module level
def test_sound_player_mixer_not_available_no_errors(mock_mixer_module):
    """Edge case: SoundPlayer initializes and runs without errors if mixer is not available."""
    # Arrange
    mock_mixer_module.init.side_effect = Exception("Mixer init failed") # Simulate init failure
    sounds_root_path = Path("dummy_path") # Doesn't need to exist for this test

    # Act & Assert (no exception should be raised)
    sp = SoundPlayer(sounds_root_path)
    sp.update("move") # Should not crash
    assert sp.sounds["move"] is None # Sound should not be loaded
    mock_mixer_module.Sound.assert_not_called() # Sound constructor should not be called
    mock_mixer_module.init.assert_called_once() # mixer.init should have been attempted