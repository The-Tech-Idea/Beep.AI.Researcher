import inspect, re, json, glob, os

print("=== COMPREHENSIVE CODE VALIDATION ===")
print()

# 1. SERVICE METHODS VALIDATION
print("1. SERVICE METHODS")

from app.services.recommendation_service import RecommendationService
from app.services.alert_service import AlertService
from app.services.reading_list_service import ReadingListService
from app.services.interest_profile_service import InterestProfileService
from app.services.smart_import_service import SmartImportService
from app.services.deduplication_service import DeduplicationService
from app.services.evidence_synthesis_service import EvidenceSynthesisService
from app.services.auto_extraction_service import AutoExtractionService
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.writing_quality_service import WritingQualityService
from app.services.citation_draft_service import CitationDraftService
from app.services.readability_service import ReadabilityService
from app.services.polarity_classifier import PolarityClassifier
from app.services.literature_review_draft_service import LiteratureReviewDraftService
from app.services.retraction_alert_service import RetractionAlertService
from app.services.retraction_watch_adapter import RetractionWatchAdapter
from app.services.library_analytics_service import LibraryAnalyticsService
from app.services.project_service import ProjectService

services = {
    "RecommendationService": RecommendationService,
    "AlertService": AlertService,
    "ReadingListService": ReadingListService,
    "InterestProfileService": InterestProfileService,
    "SmartImportService": SmartImportService,
    "DeduplicationService": DeduplicationService,
    "EvidenceSynthesisService": EvidenceSynthesisService,
    "AutoExtractionService": AutoExtractionService,
    "KnowledgeGraphService": KnowledgeGraphService,
    "WritingQualityService": WritingQualityService,
    "CitationDraftService": CitationDraftService,
    "ReadabilityService": ReadabilityService,
    "PolarityClassifier": PolarityClassifier,
    "LiteratureReviewDraftService": LiteratureReviewDraftService,
    "RetractionAlertService": RetractionAlertService,
    "RetractionWatchAdapter": RetractionWatchAdapter,
    "LibraryAnalyticsService": LibraryAnalyticsService,
    "ProjectService": ProjectService,
}

total_methods = 0
for svc_name, svc_cls in services.items():
    count = 0
    for m in dir(svc_cls):
        if m.startswith("_"):
            continue
        method = getattr(svc_cls, m)
        if callable(method):
            try:
                inspect.signature(method)
                count += 1
            except ValueError:
                print(f"  ERROR: {svc_name}.{m}: invalid signature")
    total_methods += count
    print(f"  {svc_name}: {count} methods")

print(f"  Total: {total_methods} public methods validated")

# 2. FETCH URL VALIDATION
print()
print("2. FETCH URL TO ROUTE MAPPING")

from app import create_app

app = create_app()

route_patterns = set()
for rule in app.url_map.iter_rules():
    if rule.endpoint == "static":
        continue
    route_patterns.add(rule.rule)

js_files = glob.glob("static/js/**/*.js", recursive=True)
missing_routes = []
total_fetches = 0

for js in js_files:
    if "/vendor/" in js:
        continue
    try:
        with open(js, "r", encoding="utf-8") as f:
            content = f.read()
    except:
        continue
    for match in re.finditer(r"fetch\('(/[^']+)'", content):
        url = match.group(1)
        total_fetches += 1
        found = False
        for pattern in route_patterns:
            p = re.sub(r"<[^>]+>", r"[^/]+", pattern)
            if re.match(p + "$", url):
                found = True
                break
        if not found:
            missing_routes.append((os.path.basename(js), url))

print(f"  Fetch URLs checked: {total_fetches}")
if missing_routes:
    print(f"  Gaps ({len(missing_routes)}):")
    for js, url in missing_routes[:20]:
        print(f"    {url} <- {js}")
else:
    print("  All fetch URLs match: OK")

# 3. i18n KEY VALIDATION
print()
print("3. i18n KEY COVERAGE")

with open("locales/en.json", "r", encoding="utf-8") as f:
    en = json.load(f)
en_keys = set(en.keys())

dom_tags = {
    "div",
    "li",
    "span",
    "option",
    "tr",
    "a",
    "canvas",
    "table",
    "td",
    "th",
    "thead",
    "tbody",
    "ul",
    "ol",
    "h5",
    "h6",
    "p",
    "button",
    "input",
    "select",
    "form",
    "label",
    "img",
    "script",
    "link",
    "meta",
    "style",
    "head",
    "body",
    "html",
    "nav",
    "main",
    "section",
    "article",
    "aside",
    "header",
    "footer",
    "details",
    "summary",
    "dialog",
    "modal",
}

template_missing = {}
for tmpl in glob.glob("templates/**/*.html", recursive=True):
    try:
        with open(tmpl, "r", encoding="utf-8") as f:
            content = f.read()
        for match in re.finditer(r"t\('([a-zA-Z_][a-zA-Z0-9_.]*)'", content):
            key = match.group(1)
            if key not in en_keys and key not in template_missing:
                template_missing[key] = os.path.basename(tmpl)
    except:
        pass

js_missing = {}
for js in glob.glob("static/js/**/*.js", recursive=True):
    if "/vendor/" in js:
        continue
    try:
        with open(js, "r", encoding="utf-8") as f:
            content = f.read()
        for match in re.finditer(r"t\('([a-zA-Z_][a-zA-Z0-9_.]*)'", content):
            key = match.group(1)
            if key.lower() in dom_tags:
                continue
            if key not in en_keys and key not in js_missing:
                js_missing[key] = os.path.basename(js)
    except:
        pass

print(f"  Keys in en.json: {len(en_keys)}")
if template_missing:
    print(f"  Missing in templates: {len(template_missing)}")
    for k, v in sorted(template_missing.items())[:10]:
        print(f"    {k} <- {v}")
if js_missing:
    print(f"  Missing in JS: {len(js_missing)}")
    for k, v in sorted(js_missing.items())[:10]:
        print(f"    {k} <- {v}")

# 4. BEEP_I18N COMPLETENESS
print()
print("4. BEEP_I18N BLOCK COMPLETENESS")

checks = [
    ("templates/synthesis/synthesis.html", "static/js/synthesis/synthesis.js"),
    (
        "templates/knowledge_map/knowledge_map.html",
        "static/js/knowledge_map/knowledge_map.js",
    ),
    (
        "templates/knowledge_map/global_map.html",
        "static/js/knowledge_map/global_map.js",
    ),
    ("templates/references/analytics.html", "static/js/references/analytics.js"),
    (
        "templates/references/citation_context.html",
        "static/js/references/citation_context.js",
    ),
    ("templates/project/report.html", "static/js/project/writing_assistant.js"),
]

bip_ok = True
for tmpl, js in checks:
    try:
        with open(tmpl, "r", encoding="utf-8") as f:
            tcontent = f.read()
        match = re.search(
            r"window\.BEEP_I18N\s*=\s*\{(.*?)\};\s*</script>", tcontent, re.DOTALL
        )
        template_keys = set()
        if match:
            for k in re.findall(r"'([a-zA-Z_][a-zA-Z0-9_.]*)'", match.group(1)):
                template_keys.add(k)
    except:
        continue

    try:
        with open(js, "r", encoding="utf-8") as f:
            jcontent = f.read()
        js_keys = set()
        for m in re.finditer(r"t\('([a-zA-Z_][a-zA-Z0-9_.]*)'", jcontent):
            k = m.group(1)
            if k.lower() not in dom_tags:
                js_keys.add(k)

        missing = js_keys - template_keys
        if missing:
            print(f"  MISSING: {os.path.basename(js)}")
            for k in sorted(missing):
                print(f"    {k}")
            bip_ok = False
    except:
        pass

if bip_ok:
    print("  All BEEP_I18N blocks complete: OK")

# 5. APP STATUS
print()
print("5. APP STATUS")

routes = [r for r in app.url_map.iter_rules() if r.endpoint != "static"]
print(f"  Routes: {len(routes)}")
print(f"  Blueprints: {len(app.blueprints)}")

for prefix in ["synthesis", "knowledge_map", "admin_packages"]:
    rts = [r for r in routes if prefix in r.endpoint]
    print(f"  {prefix}: {len(rts)} routes")

print()
print("=== VALIDATION COMPLETE ===")
