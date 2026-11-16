"""Create a repeatable SAMPLE dataset for development and demos.

All universities, programs, people and funding below are fictional and are
marked as sample data. Real program information should be added by
administrators and kept current with the ``retrieve_programs`` command.
Deadlines are generated relative to today so the demo never goes stale.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from programs.models import Faculty, FundingOpportunity, GraduateProgram, University


SAMPLE_NOTE = "Sample data for demonstration only."

UNIVERSITIES = [
    {"key": "gcsu", "name": "Gulf Coast State University (Sample)", "city": "Corpus Christi", "state_or_region": "Texas", "country": "United States", "website_url": "https://www.gulfcoast-state.example/"},
    {"key": "lsit", "name": "Lone Star Institute of Technology (Sample)", "city": "Austin", "state_or_region": "Texas", "country": "United States", "website_url": "https://www.lonestar-tech.example/"},
    {"key": "pru", "name": "Pacific Ridge University (Sample)", "city": "San Diego", "state_or_region": "California", "country": "United States", "website_url": "https://www.pacificridge.example/"},
    {"key": "hvu", "name": "Harborview University (Sample)", "city": "Boston", "state_or_region": "Massachusetts", "country": "United States", "website_url": "https://www.harborview.example/"},
    {"key": "glu", "name": "Great Lakes Metropolitan University (Sample)", "city": "Chicago", "state_or_region": "Illinois", "country": "United States", "website_url": "https://www.greatlakes-metro.example/"},
    {"key": "mlis", "name": "Maple Leaf Institute of Science (Sample)", "city": "Toronto", "state_or_region": "Ontario", "country": "Canada", "website_url": "https://www.mapleleaf-science.example/"},
]

# (key, university, name, degree, field, department, tuition, min_gpa, funding, deadline_in_days, description, requirements, funding_details)
PROGRAMS = [
    ("gcsu-cs-ms", "gcsu", "Computer Science", "masters", "Computer Science", "Department of Computing Sciences", 18000, "3.00", True, 75,
     "Thesis and non-thesis tracks in software engineering, machine learning, cybersecurity and data systems.",
     "Bachelor's degree in computing or related field; GPA 3.0; statement of purpose; two recommendation letters; GRE optional.",
     "Teaching and research assistantships with partial tuition waivers are available."),
    ("gcsu-cs-phd", "gcsu", "Computer Science", "doctoral", "Computer Science", "Department of Computing Sciences", 18500, "3.30", True, 45,
     "Research doctorate with strengths in coastal sensing, geospatial AI and human-computer interaction.",
     "Master's or strong bachelor's in computing; GPA 3.3; research statement; three letters; interview with faculty.",
     "All admitted PhD students are considered for funded research assistantships."),
    ("gcsu-marine-phd", "gcsu", "Marine Biology", "doctoral", "Marine Biology", "Department of Life Sciences", 17500, "3.20", True, 60,
     "Interdisciplinary doctorate focused on coastal ecosystems, fisheries and marine conservation.",
     "Bachelor's or master's in biology or related field; research statement; three letters.",
     "Research assistantships funded through coastal research grants."),
    ("lsit-ds-ms", "lsit", "Data Science", "masters", "Data Science", "School of Information", 32000, "3.00", False, 100,
     "Professional master's covering statistics, machine learning, data engineering and data visualization.",
     "Bachelor's degree with calculus, linear algebra and programming; GPA 3.0; resume; statement of purpose.",
     ""),
    ("lsit-ece-ms", "lsit", "Electrical and Computer Engineering", "masters", "Electrical Engineering", "Department of Electrical and Computer Engineering", 30500, "3.20", True, 20,
     "Specializations in embedded systems, signal processing, robotics and power systems.",
     "Bachelor's in electrical or computer engineering; GPA 3.2; two letters.",
     "Limited teaching assistantships for second-year students."),
    ("lsit-ai-phd", "lsit", "Artificial Intelligence", "doctoral", "Artificial Intelligence", "Department of Computer Science", 31000, "3.50", True, 30,
     "Research doctorate in machine learning, natural language processing, robotics and trustworthy AI.",
     "Strong background in mathematics and programming; GPA 3.5; research statement; three letters.",
     "Five-year funding packages including stipend and full tuition coverage."),
    ("pru-cyber-ms", "pru", "Cybersecurity", "masters", "Cybersecurity", "Department of Computer Science", 28000, "3.00", False, 120,
     "Hands-on program in network security, cryptography, digital forensics and secure software.",
     "Bachelor's in computing or IT; GPA 3.0; statement of purpose; resume.",
     ""),
    ("pru-env-ms", "pru", "Environmental Science", "masters", "Environmental Science", "School of Earth and Ocean Sciences", 26500, "2.90", True, 90,
     "Climate science, ocean-atmosphere interactions and environmental data analysis.",
     "Bachelor's in a natural science or engineering; GPA 2.9; two letters.",
     "Graduate research fellowships available on a competitive basis."),
    ("hvu-mph", "hvu", "Public Health (MPH)", "masters", "Public Health", "School of Public Health", 41000, "3.00", True, 110,
     "Concentrations in epidemiology, biostatistics, global health and health policy.",
     "Bachelor's degree; GPA 3.0; statement of purpose; three letters; public health experience preferred.",
     "Merit scholarships covering 25-50% of tuition."),
    ("hvu-me-phd", "hvu", "Mechanical Engineering", "doctoral", "Mechanical Engineering", "Department of Mechanical Engineering", 45000, "3.40", True, -10,
     "Doctoral research in robotics, biomechanics, energy systems and advanced manufacturing.",
     "Bachelor's or master's in engineering; GPA 3.4; research statement; three letters.",
     "Fully funded research assistantships."),
    ("glu-mba", "glu", "Business Administration (MBA)", "masters", "Business Administration", "School of Business", 52000, None, True, 140,
     "Full-time MBA with concentrations in analytics, finance, operations and entrepreneurship.",
     "Bachelor's degree; two years of work experience recommended; essays; one letter.",
     "Merit fellowships and graduate assistant positions."),
    ("glu-cs-ms", "glu", "Computer Science", "masters", "Computer Science", "Department of Computer Science", 34000, "3.00", False, 50,
     "Flexible master's with tracks in software systems, data science and artificial intelligence.",
     "Bachelor's degree with programming coursework; GPA 3.0; two letters.",
     ""),
    ("mlis-cs-ms", "mlis", "Computer Science", "masters", "Computer Science", "Department of Computer Science", 24000, "3.30", True, 35,
     "Research-based master's in machine learning, computer vision and distributed systems.",
     "Four-year bachelor's in computer science; GPA equivalent to 3.3; English proficiency for international applicants.",
     "Research stipends are provided to all thesis-based students."),
    ("mlis-ds-ms", "mlis", "Data Science", "masters", "Data Science", "School of Data Science", 26000, "3.00", False, None,
     "Course-based master's in applied statistics, machine learning and data ethics.",
     "Bachelor's with statistics and programming; GPA equivalent to 3.0.",
     ""),
]

# (university, name, title, department, research areas, accepting_students, program keys, bio)
FACULTY = [
    ("gcsu", "Dr. Elena Marquez", "Associate Professor", "Computing Sciences", "machine learning, geospatial AI, coastal sensing", True, ["gcsu-cs-ms", "gcsu-cs-phd"], "Builds machine-learning models for coastal monitoring and hurricane impact prediction."),
    ("gcsu", "Dr. Samuel Okafor", "Professor", "Computing Sciences", "cybersecurity, network security, IoT security", True, ["gcsu-cs-ms", "gcsu-cs-phd"], "Studies security of connected devices and critical infrastructure."),
    ("gcsu", "Dr. Priya Raman", "Assistant Professor", "Computing Sciences", "human-computer interaction, accessibility, software engineering", None, ["gcsu-cs-ms"], "Designs accessible software for people with low vision."),
    ("gcsu", "Dr. Hannah Lindqvist", "Associate Professor", "Life Sciences", "marine ecology, fisheries, coral reef conservation", True, ["gcsu-marine-phd"], "Leads long-term monitoring of Gulf of Mexico reef systems."),
    ("lsit", "Dr. Marcus Chen", "Professor", "Computer Science", "natural language processing, large language models, trustworthy AI", True, ["lsit-ai-phd", "lsit-ds-ms"], "Researches reliable and explainable language models."),
    ("lsit", "Dr. Aisha Bello", "Assistant Professor", "Computer Science", "robotics, reinforcement learning, computer vision", True, ["lsit-ai-phd", "lsit-ece-ms"], "Teaches robots to learn manipulation skills from demonstration."),
    ("lsit", "Dr. Tomás Herrera", "Associate Professor", "Electrical and Computer Engineering", "embedded systems, signal processing, wireless networks", False, ["lsit-ece-ms"], "Works on low-power wireless sensing platforms."),
    ("lsit", "Dr. Grace Whitfield", "Professor", "School of Information", "data visualization, statistics, data ethics", None, ["lsit-ds-ms"], "Studies how people interpret charts and uncertainty."),
    ("pru", "Dr. Kenji Watanabe", "Associate Professor", "Computer Science", "cryptography, applied security, digital forensics", True, ["pru-cyber-ms"], "Develops practical cryptographic protocols."),
    ("pru", "Dr. Leila Haddad", "Professor", "Earth Sciences", "climate modeling, oceanography, environmental data science", True, ["pru-env-ms"], "Models ocean-atmosphere interactions using machine learning."),
    ("hvu", "Dr. Nadia Petrova", "Associate Professor", "Public Health", "epidemiology, biostatistics, global health", True, ["hvu-mph"], "Studies infectious disease transmission in urban settings."),
    ("hvu", "Dr. Robert Asante", "Professor", "Mechanical Engineering", "robotics, biomechanics, medical devices", True, ["hvu-me-phd"], "Designs wearable robotic devices for rehabilitation."),
    ("glu", "Dr. Olivia Brennan", "Professor", "School of Business", "business analytics, operations research, supply chains", None, ["glu-mba"], "Applies optimization to supply-chain resilience."),
    ("glu", "Dr. Daniel Kim", "Assistant Professor", "Computer Science", "distributed systems, cloud computing, software engineering", True, ["glu-cs-ms"], "Builds tools for reliable cloud software."),
    ("mlis", "Dr. Sophie Tremblay", "Associate Professor", "Computer Science", "computer vision, machine learning, medical imaging", True, ["mlis-cs-ms", "mlis-ds-ms"], "Develops deep-learning methods for medical image analysis."),
    ("mlis", "Dr. Arjun Mehta", "Professor", "School of Data Science", "statistics, causal inference, data ethics", False, ["mlis-ds-ms"], "Researches fair and causal machine learning."),
]

# (name, type, university or None, program key or None, provider, amount, note, covers_tuition, international, degree_levels, deadline_in_days, eligibility, description)
FUNDING = [
    ("Graduate Research Assistantship - Computing", "assistantship", "gcsu", "gcsu-cs-phd", "", 24000, "per year stipend plus tuition waiver", True, True, "doctoral", 45, "Admitted PhD students in good standing.", "Research positions funded by faculty grants."),
    ("Computing Teaching Assistantship", "assistantship", "gcsu", "gcsu-cs-ms", "", 12000, "per academic year, partial tuition waiver", False, True, "masters", 60, "Full-time master's students with strong communication skills.", "Assist with undergraduate programming courses."),
    ("Coastal Research Fellowship", "fellowship", "gcsu", "gcsu-marine-phd", "", 28000, "per year for up to 4 years", True, True, "doctoral", 50, "Doctoral applicants in marine or environmental sciences.", "Supports research on Gulf coastal ecosystems."),
    ("Trustworthy AI Doctoral Fellowship", "fellowship", "lsit", "lsit-ai-phd", "", 38000, "per year plus full tuition", True, True, "doctoral", 25, "First-year PhD applicants in AI or machine learning.", "Five-year fellowship for research on reliable AI."),
    ("Lone Star Engineering Scholarship", "scholarship", "lsit", None, "", 5000, "one-time award", False, False, "masters", 80, "Texas residents admitted to an engineering master's program.", "Merit scholarship for engineering graduate students."),
    ("Ocean and Climate Graduate Fellowship", "fellowship", "pru", "pru-env-ms", "", 20000, "per year", False, True, "masters", 70, "Admitted environmental science students with research experience.", "Competitive fellowship for climate research."),
    ("Public Health Merit Scholarship", "scholarship", "hvu", "hvu-mph", "", 15000, "per year (about 35% of tuition)", False, True, "masters", 110, "All MPH applicants are considered automatically.", "Merit-based tuition scholarship."),
    ("MBA Analytics Fellowship", "fellowship", "glu", "glu-mba", "", 20000, "per year", False, True, "masters", 120, "MBA applicants with quantitative backgrounds.", "Fellowship for students in the analytics concentration."),
    ("Maple Leaf International Excellence Award", "scholarship", "mlis", None, "", 10000, "one-time award", False, True, "", 30, "International students admitted to any graduate program.", "Entrance award for high-achieving international students."),
    ("Women in Computing Graduate Scholarship", "scholarship", None, None, "Sample Computing Foundation", 8000, "one-time award", False, True, "masters,doctoral", 55, "Women pursuing graduate study in computing fields.", "External scholarship open to students at any university."),
    ("First-Generation Graduate Student Grant", "grant", None, None, "Sample Education Trust", 3000, "one-time award", False, False, "", 95, "First-generation college graduates entering graduate school in the U.S.", "Helps cover application fees, relocation and books."),
]


class Command(BaseCommand):
    help = "Create a repeatable, clearly-labelled SAMPLE dataset for development and demos."

    @transaction.atomic
    def handle(self, *args, **options):
        today = date.today()

        def due(days):
            return today + timedelta(days=days) if days is not None else None

        # Deactivate Iteration 1 placeholder records that used real university names.
        GraduateProgram.objects.filter(description="Sample record for Iteration 1 testing.").update(is_active=False)

        universities = {}
        for data in UNIVERSITIES:
            data = dict(data)
            key = data.pop("key")
            universities[key], _ = University.objects.update_or_create(name=data["name"], defaults=data)

        programs = {}
        for (key, uni, name, degree, field, dept, tuition, gpa, funding, deadline, desc, reqs, funding_details) in PROGRAMS:
            university = universities[uni]
            slug = key.split("-", 1)[1]
            programs[key], _ = GraduateProgram.objects.update_or_create(
                university=university,
                name=name,
                degree_level=degree,
                defaults={
                    "field_of_study": field,
                    "department": dept,
                    "description": f"{desc} {SAMPLE_NOTE}",
                    "admission_requirements": reqs,
                    "minimum_gpa": gpa,
                    "tuition_per_year": tuition,
                    "funding_available": funding,
                    "funding_details": funding_details,
                    "application_deadline": due(deadline),
                    "program_url": f"{university.website_url}graduate/{slug}",
                    "is_active": True,
                    "origin": "sample",
                },
            )

        for (uni, name, title, dept, areas, accepting, program_keys, bio) in FACULTY:
            university = universities[uni]
            member, _ = Faculty.objects.update_or_create(
                university=university,
                name=name,
                defaults={
                    "title": title,
                    "department": dept,
                    "research_areas": areas,
                    "accepting_students": accepting,
                    "bio": f"{bio} (Fictional sample profile.)",
                    "email": f"{name.split()[-1].lower()}@{university.website_url.split('//')[1].strip('/').replace('www.', '')}",
                    "profile_url": f"{university.website_url}people/{name.split()[-1].lower()}",
                    "origin": "sample",
                },
            )
            member.programs.set([programs[key] for key in program_keys])

        for (name, ftype, uni, program_key, provider, amount, note, covers, intl, levels, deadline, eligibility, desc) in FUNDING:
            university = universities[uni] if uni else None
            FundingOpportunity.objects.update_or_create(
                name=name,
                defaults={
                    "funding_type": ftype,
                    "university": university,
                    "program": programs[program_key] if program_key else None,
                    "provider": provider or (university.name if university else ""),
                    "amount": amount,
                    "amount_note": note,
                    "covers_tuition": covers,
                    "international_eligible": intl,
                    "degree_levels": levels,
                    "deadline": due(deadline),
                    "eligibility": eligibility,
                    "description": f"{desc} {SAMPLE_NOTE}",
                    "url": f"{university.website_url}funding" if university else "https://www.scholarships.example/",
                    "is_active": True,
                    "origin": "sample",
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Sample data ready: {len(universities)} universities, {len(programs)} programs, "
            f"{len(FACULTY)} faculty, {len(FUNDING)} funding opportunities."
        ))
