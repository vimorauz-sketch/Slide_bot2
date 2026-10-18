from services.template_service import template_manager


def test_all_ten_templates_are_listed_with_names():
    tpls = template_manager.get_all_templates()
    assert len(tpls) == 200
    assert all(t["name"] and t["code"] for t in tpls)


def test_template_code_and_id_resolve_to_the_same_template():
    assert template_manager.get_template("09")["id"] == template_manager.get_template("09_uzbek_heritage")["id"]
    assert template_manager.get_template("tpl_03_aurora_gradient")["id"] == "03_aurora_gradient"


def test_design_system_exposes_palette_and_layouts():
    ds = template_manager.get_template_design_system("06")
    assert ds["theme"]["primary"].startswith("#")
    assert "cards" in ds["layouts"]
