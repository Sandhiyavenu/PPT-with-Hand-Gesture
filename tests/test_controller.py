from PIL import Image

from app.controller import PresentationController


class FakeDocument:
    kind = "fake"

    def __init__(self, page_count: int = 5) -> None:
        self.page_count = page_count
        self.path = None

    @property
    def title(self) -> str:
        return "Fake Deck"

    def render(self, index: int):
        return Image.new("RGB", (16, 9), (index * 20 % 255, 0, 0))

    def close(self) -> None:
        pass


def make_controller() -> PresentationController:
    return PresentationController(FakeDocument())


def test_next_prev_and_clamping():
    controller = make_controller()
    assert controller.perform("next_slide") is True
    assert controller.state.index == 1
    assert controller.perform("prev_slide") is True
    assert controller.state.index == 0
    assert controller.perform("prev_slide") is False  # already first


def test_scroll_at_edge_changes_slide():
    controller = make_controller()
    # Scrolling down from the top first moves within the page.
    assert controller.perform("scroll_down") is True
    assert controller.state.index == 0
    assert 0 < controller.state.scroll <= 1.0

    for _ in range(20):
        controller.perform("scroll_down")
    assert controller.state.index == 1


def test_zoom_is_clamped():
    controller = make_controller()
    for _ in range(20):
        controller.perform("zoom_in")
    assert controller.state.zoom == 5.0
    for _ in range(40):
        controller.perform("zoom_out")
    assert controller.state.zoom == 1.0


def test_toggles():
    controller = make_controller()
    controller.perform("toggle_pause")
    assert controller.state.paused is True
    controller.perform("toggle_pause")
    assert controller.state.paused is False

    controller.perform("toggle_pointer")
    assert controller.state.pointer_enabled is True

    controller.perform("toggle_presentation")
    assert controller.state.presenting is True


def test_commands_enabled_rules():
    controller = make_controller()
    assert controller.commands_enabled() is True
    controller.perform("toggle_pause")
    assert controller.commands_enabled() is False
    controller.perform("toggle_pause")
    controller.state.tracking_reliable = False
    assert controller.commands_enabled() is False


def test_revision_increments_on_change():
    controller = make_controller()
    before = controller.state.revision
    controller.perform("next_slide")
    assert controller.state.revision == before + 1
    controller.perform("prev_slide")
    controller.perform("prev_slide")  # no change
    assert controller.state.revision == before + 2
