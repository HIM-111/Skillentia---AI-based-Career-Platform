from app.services.skill_extractor import extract_skills


def test_extract_skills_healthcare_domain():
    text = (
        "Registered nurse with Epic EHR experience, HIPAA compliance, "
        "patient care, triage, and medication administration."
    )
    skills = extract_skills(text)
    assert "epic" in skills
    assert "electronic health records" in skills
    assert "hipaa" in skills
    assert "patient care" in skills
    assert "triage" in skills


def test_extract_skills_finance_domain():
    text = (
        "Accountant with GAAP knowledge, forecasting, budgeting, "
        "accounts payable/accounts receivable, and QuickBooks."
    )
    skills = extract_skills(text)
    assert "gaap" in skills
    assert "forecasting" in skills
    assert "budgeting" in skills
    assert "accounts payable" in skills
    assert "accounts receivable" in skills
    assert "quickbooks" in skills


def test_extract_skills_operations_domain():
    text = (
        "Operations lead with supply chain, inventory management, WMS, "
        "lean six sigma, forklift operation, and OSHA safety."
    )
    skills = extract_skills(text)
    assert "supply chain" in skills
    assert "inventory management" in skills
    assert "warehouse management" in skills
    assert "lean" in skills
    assert "six sigma" in skills
    assert "forklift operation" in skills
    assert "osha" in skills
