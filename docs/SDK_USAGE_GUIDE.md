# Beep.AI SDK Usage Guide for Researcher

**Last Updated**: February 6, 2026  
**SDK Version**: 1.0 (DotNet & Python parity)

---

## Overview

Both DotNet and Python SDKs now have complete parity. This guide shows how Beep.AI.Researcher should integrate the latest SDK methods.

---

## Installation

### Python

```bash
pip install beep-ai-sdk
```

### .NET

```bash
dotnet add package Beep.AI.Middleware
```

---

## API Authentication

All endpoints require an API token created in `/admin/applications`:

```python
from beep_ai_sdk import AIMiddlewareClient

client = AIMiddlewareClient(
    base_url="http://localhost:5000/ai-middleware",
    api_token="your_token_here"
)
```

```csharp
using Beep.AI.Middleware;

var client = new AIMiddlewareClient(
    "http://localhost:5000/ai-middleware",
    "YOUR_API_TOKEN"
);
```

---

## 1. App User Management (NEW in Python SDK)

### Register User

**Python**:
```python
user = client.register_app_user(
    user_id="user_123",
    display_name="John Doe",
    email="john@example.com",
    tier="premium",
    role="researcher",
    metadata={"organization": "MIT", "institution_type": "university"}
)
```

**C#**:
```csharp
var user = await client.RegisterAppUserAsync(
    userId: "user_123",
    displayName: "John Doe",
    email: "john@example.com",
    tier: "premium",
    role: "researcher",
    metadata: new Dictionary<string, object?>
    {
        ["organization"] = "MIT",
        ["institution_type"] = "university"
    }
);
```

### Get User Info

**Python**:
```python
user = client.get_app_user("user_123")
print(user["data"]["display_name"])

# Get usage statistics
usage = client.get_app_user_usage("user_123")
print(f"Requests used: {usage['data']['requests_used']}")
```

### Update User

**Python**:
```python
updated = client.update_app_user(
    user_id="user_123",
    display_name="John Smith",
    is_active=True,
    metadata={"department": "Research"}
)
```

### Change User Tier

**Python**:
```python
# Upgrade or downgrade tier
result = client.set_app_user_tier("user_123", "enterprise")
```

### Delete User

**Python**:
```python
# Delete user without deleting their data
result = client.delete_app_user("user_123", delete_data=False)

# Delete user AND cascade-delete their RAG documents and collections
result = client.delete_app_user("user_123", delete_data=True)
print(f"Deleted {result['deleted_documents']} documents")
print(f"Deleted {result['deleted_collections']} collections")
```

### List All Users

**Python**:
```python
# List all users (with pagination)
users = client.list_app_users(page=1, per_page=50)
print(f"Total users: {users['total']}")
print(f"Pages: {users['pages']}")

for user in users["users"]:
    print(f"{user['user_id']}: {user['display_name']} ({user['tier']})")

# Filter by tier
premium_users = client.list_app_users(tier="premium", per_page=25)

# Filter by active status
active_users = client.list_app_users(is_active=True, page=1, per_page=100)

# Search users by ID, name, or email
search_results = client.list_app_users(search="john", page=1, per_page=25)

# Combine filters: active premium users matching "research"
results = client.list_app_users(
    page=1,
    per_page=50,
    tier="premium",
    is_active=True,
    search="research"
)
```

### List Available Tiers

**Python**:
```python
tiers = client.list_tiers()
for tier in tiers["data"]:
    print(f"{tier['name']}: {tier['description']}")
```

---

## 2. User-Scoped RAG Collections (NEW in Python SDK)

### Create Collection for User

**Python**:
```python
collection = client.create_user_collection(
    user_id="user_123",
    name="Tumor Research 2024",
    description="Research papers on oncology",
    is_public=False,  # Only owner can access
    allowed_tiers=["premium", "enterprise"],  # Or None for owner-only
    metadata={"category": "medical", "year": 2024}
)
print(f"Created collection: {collection['data']['id']}")
```

### List User's Collections

**Python**:
```python
# User's own + public collections
collections = client.list_user_collections(
    user_id="user_123",
    include_public=True
)

for coll in collections["data"]:
    print(f"{coll['name']} ({coll['owner_id']})")
    print(f"  Public: {coll['is_public']}")
    print(f"  Documents: {coll['document_count']}")
```

### Get Collection Details

**Python**:
```python
# Get collection with access control verification
collection = client.get_user_collection(
    collection_id="coll_abc123",
    user_id="user_123"  # Optional - passed as X-User-ID header for permission verification
)
print(f"Collection name: {collection['name']}")
print(f"Documents: {len(collection.get('documents', []))}")
print(f"Owner: {collection['owner_id']}")
```

### Update Collection

**Python**:
```python
updated = client.update_user_collection(
    collection_id="coll_abc123",
    user_id="user_123",
    description="Updated research papers",
    is_public=True,  # Make public
    allowed_tiers=["free", "premium"]  # Allow free tier users
)
```

### Delete Collection

**Python**:
```python
result = client.delete_user_collection(
    collection_id="coll_abc123",
    user_id="user_123"
)
print(f"Deleted: {result['success']}")
```

---

## 3. Chat & Tools (Existing + Enhanced)

### Chat with LLM

**Python**:
```python
response = client.chat([
    {"role": "user", "content": "Explain diabetes treatment options"}
])

print(response["choices"][0]["message"]["content"])
```

### Chat with Tools/Functions

**Python**:
```python
# Auto-loads all available tools
response = client.chat_with_tools(
    messages=[
        {"role": "user", "content": "Create a bar chart of COVID cases by month"}
    ],
    tool_choice="auto",  # Let model decide if tool needed
    auto_execute_tools=True  # Auto-execute returned tool calls
)

# Response includes tool results
print(response["choices"][0]["message"]["content"])
```

### Vision: Classify Image

**Python**:
```python
result = client.classify_image(
    image_url="https://example.com/pathology.png"
)
print(f"Detected: {result['labels']}")
```

### Vision: Extract Text (OCR)

**Python**:
```python
result = client.extract_image_text(
    image_url="https://example.com/medical_report.pdf"
)
print(result["text"])
```

### Document Extraction

**Python**:
```python
# Extract structured data from document
result = client.extract_document("path/to/document.pdf")
print(result["extracted_data"])
```

---

## 4. Researcher Integration Examples

### Example 1: Register New Researcher

```python
from beep_ai_sdk import AIMiddlewareClient

client = AIMiddlewareClient(
    "http://localhost:5000/ai-middleware",
    api_token="admin_token"
)

# When user signs up in Researcher
new_user = client.register_app_user(
    user_id=f"researcher_{user.id}",
    display_name=user.full_name,
    email=user.email,
    tier="free",
    role="researcher",
    metadata={
        "researcher_id": user.id,
        "institution": user.institution,
        "field": user.research_field
    }
)

if new_user["success"]:
    print(f"User registered in AI Middleware")
```

### Example 2: Create Project Collection

```python
# When researcher creates a project in Beep.AI.Researcher
project = create_research_project(title="Diabetes Study")
researcher_id = get_current_user_id()

# Create RAG collection in AI Middleware
collection = client.create_user_collection(
    user_id=f"researcher_{researcher_id}",
    name=project.title,
    description=project.description,
    is_public=False,  # Private by default
    metadata={
        "project_id": project.id,
        "research_type": project.type,
        "institution": project.institution
    }
)

# Link collection in Researcher database
project.ai_collection_id = collection["data"]["id"]
project.save()
```

### Example 3: Extract Data from Research Document

```python
# User uploads research paper to Researcher
document = upload_document(file, project)

# Extract structured data from document
extraction_result = client.extract_document(file.path)

# Save extracted data
store_extracted_fields(
    document_id=document.id,
    extracted_data=extraction_result["extracted_data"]
)

# Store extracted entities (cohort, interventions, outcomes)
for entity in extraction_result["entities"]:
    create_extracted_entity(
        document_id=document.id,
        entity_type=entity["type"],
        value=entity["value"],
        confidence=entity.get("confidence", 1.0)
    )
```

### Example 4: Chat About Research Documents

```python
# Researcher asks question about project
question = "What are the common adverse effects mentioned?"
project_id = request.args.get("project_id")

# Build context from project documents
documents = get_project_documents(project_id)
document_summaries = "\n".join([
    f"- {doc.title}: {doc.summary}"
    for doc in documents
])

# Chat with context
response = client.chat([
    {
        "role": "system",
        "content": f"You are analyzing a research project. Context:\n{document_summaries}"
    },
    {
        "role": "user",
        "content": question
    }
])

answer = response["choices"][0]["message"]["content"]
return {"answer": answer}
```

### Example 5: Analyze Research Image/Scan

```python
# Researcher uploads medical image
image = upload_image(file, project)

# Extract text from image (OCR)
ocr_result = client.extract_image_text(image.url)
save_ocr_text(image_id=image.id, text=ocr_result["text"])

# Classify image
classification = client.classify_image(image.url)
image.classification = classification["labels"]
image.save()

# Detect objects in image (if applicable)
detection = client.detect_objects(image.url, threshold=0.7)
for obj in detection["objects"]:
    create_detected_object(
        image_id=image.id,
        label=obj["label"],
        confidence=obj["confidence"],
        bbox=obj["bbox"]
    )
```

---

## Token Scopes

When creating API tokens in `/admin/applications`, assign appropriate scopes:

| Scope | Purpose | For Researcher Use |
|-------|---------|-------------------|
| `llm:read` | Query LLM | Chat questions ✓ |
| `llm:write` | Execute LLM | ✗ Not used |
| `rag:read` | Search RAG collections | Search documents ✓ |
| `rag:write` | Upload to RAG | Ingest documents ✓ |
| `ml:read` | Use ML models | Vision analysis ✓ |
| `ml:write` | Fine-tune models | ✗ Not used |
| `admin:read` | Read system config | List available tools ✓ |
| `admin:write` | Modify config | ✗ Not used |

**Recommended token scopes for Researcher**:
```
llm:read,rag:read,rag:write,ml:read,admin:read
```

---

## Error Handling

### Python

```python
from beep_ai_sdk import BeepAIError

try:
    user = client.get_app_user("invalid_user")
except BeepAIError as e:
    print(f"Error: {e.message}")
    print(f"Status: {e.status_code}")
    print(f"Payload: {e.payload}")
```

### Response Format

```json
{
    "success": false,
    "error": "User not found",
    "error_code": "USER_NOT_FOUND",
    "data": null
}
```

---

## Rate Limiting

API requests are rate-limited per user tier:

| Tier | Requests/Hour | Documents | Collections |
|------|---------------|-----------|-------------|
| free | 100 | 50 | 5 |
| premium | 1000 | 500 | 50 |
| enterprise | Unlimited | Unlimited | Unlimited |

Check rate limit in response headers:
```python
response = client.chat([...])
print(f"Remaining: {response.get('x-ratelimit-remaining')}")
```

---

## Migration from V1.0 to V2.0 (Future)

When V2.0 is released:
- Existing methods remain backward-compatible
- New methods use `/api/v2/` prefix
- Deprecation warnings appear in v1.1
- V1.0 supported until June 2027

---

## Support & Documentation

- **DotNet SDK**: `/Beep.AI.Server/Beep.AI.SDK/DotNet/README.md`
- **Python SDK**: `/Beep.AI.Server/Beep.AI.SDK/Python/README.md`
- **API Reference**: Admin panel → `/admin/api-docs`
- **Issues**: GitHub → `The-Tech-Idea/Beep.AI.Server`

---

**Version**: 1.0  
**Last Updated**: February 6, 2026
