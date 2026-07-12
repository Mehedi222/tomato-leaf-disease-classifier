from theme import CLASS_COLORS

EXPECTED_CLASSES = {"Early Blight", "Healthy", "Late Blight", "Leaf Spot"}


def test_class_colors_has_exactly_the_four_classes():
    assert set(CLASS_COLORS.keys()) == EXPECTED_CLASSES


def test_class_colors_are_hex_strings():
    for color in CLASS_COLORS.values():
        assert isinstance(color, str)
        assert color.startswith("#")
        assert len(color) == 7
