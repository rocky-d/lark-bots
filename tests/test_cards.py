from lark_bots.cards import (
    at_all_element_factory,
    error_card_factory,
    finish_card_factory,
    launch_card_factory,
    local_datetime_element_factory,
)

# ===========================================================================
# local_datetime_element_factory
# ===========================================================================


class TestLocalDatetimeElementFactory:
    def test_returns_independent_copy(self) -> None:
        a = local_datetime_element_factory()
        b = local_datetime_element_factory()
        assert a == b
        assert a is not b


# ===========================================================================
# at_all_element_factory
# ===========================================================================


class TestAtAllElementFactory:
    def test_returns_independent_copy(self) -> None:
        a = at_all_element_factory()
        b = at_all_element_factory()
        assert a == b
        assert a is not b


# ===========================================================================
# launch_card_factory
# ===========================================================================


class TestLaunchCardFactory:
    def test_returns_independent_copy(self) -> None:
        a = launch_card_factory()
        b = launch_card_factory()
        assert a == b
        assert a is not b


# ===========================================================================
# finish_card_factory
# ===========================================================================


class TestFinishCardFactory:
    def test_returns_independent_copy(self) -> None:
        a = finish_card_factory()
        b = finish_card_factory()
        assert a == b
        assert a is not b


# ===========================================================================
# error_card_factory
# ===========================================================================


class TestErrorCardFactory:
    def test_returns_independent_copy(self) -> None:
        a = error_card_factory()
        b = error_card_factory()
        assert a == b
        assert a is not b
