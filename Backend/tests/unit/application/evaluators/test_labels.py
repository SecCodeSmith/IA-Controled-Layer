from control_layer.application.evaluators._labels import role_label
from control_layer.domain.models.enums import Role


def test_developer_role_label() -> None:
    assert role_label(Role.developer) == "Developer"


def test_hr_role_label_is_an_acronym() -> None:
    assert role_label(Role.hr) == "HR"


def test_finance_role_label() -> None:
    assert role_label(Role.finance) == "Finance"
