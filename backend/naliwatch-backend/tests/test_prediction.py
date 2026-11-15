from datetime import date

from app.services.prediction import PriorityInput, predict_due_date, priority_score


def test_due_date_formula():
    # 3000 L * 0.33 / (5 people * 0.15 L/day) = 1320 days
    assert predict_due_date(date(2020, 1, 1), 3000, 5, fill_limit=0.33, sludge_per_person_day=0.15) == date(2023, 8, 13)


def test_bigger_family_fills_faster():
    a = predict_due_date(date(2020, 1, 1), 3000, 3)
    b = predict_due_date(date(2020, 1, 1), 3000, 8)
    assert b < a


def test_manual_cleaning_outranks_everything():
    today = date(2026, 1, 1)
    manual, _ = priority_score(PriorityInput(today, manual_cleaning=True))
    overdue, _ = priority_score(PriorityInput(today, due_date=date(2025, 1, 1), overflow_severity=3, cluster_status="risk"))
    assert manual > overdue


def test_overdue_beats_not_due_and_reasons_are_recorded():
    today = date(2026, 1, 1)
    s1, why = priority_score(PriorityInput(today, due_date=date(2025, 12, 1)))
    s2, _ = priority_score(PriorityInput(today, due_date=date(2027, 1, 1)))
    assert s1 > s2 == 0 and why
