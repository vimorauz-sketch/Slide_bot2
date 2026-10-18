from config import Settings


def test_admin_id_list_parses_single_id():
    s = Settings(ADMIN_IDS="123456789")
    assert s.admin_id_list == [123456789]


def test_admin_id_list_parses_multiple_comma_separated_ids():
    s = Settings(ADMIN_IDS="111,222, 333")
    assert s.admin_id_list == [111, 222, 333]


def test_admin_id_list_empty_string_yields_empty_list():
    s = Settings(ADMIN_IDS="")
    assert s.admin_id_list == []


def test_admin_id_list_ignores_non_numeric_garbage():
    # A misconfigured ADMIN_IDS must never silently grant admin to everyone;
    # malformed entries are simply dropped, not treated as "no restriction".
    s = Settings(ADMIN_IDS="abc, , not_a_number")
    assert s.admin_id_list == []


def test_admin_id_list_mixed_valid_and_invalid_entries():
    s = Settings(ADMIN_IDS="123, abc, 456")
    assert s.admin_id_list == [123, 456]


def test_max_slides_default_is_greater_than_min_slides_default():
    s = Settings()
    assert s.MAX_SLIDES_PER_ORDER >= s.MIN_SLIDES_PER_ORDER
