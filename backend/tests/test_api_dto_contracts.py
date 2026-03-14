from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DTO_FILE = REPO_ROOT / "backend" / "app" / "api" / "dto.py"


def test_api_dto_contracts_are_declared() -> None:
    dto_source = DTO_FILE.read_text(encoding="utf-8")

    expected_fragments = [
        "class TagRefDto(BaseModel):",
        "class PaginatedResponse(BaseModel, Generic[ItemT]):",
        "class AsyncAcceptedDto(BaseModel):",
        "class NoteCardDto(BaseModel):",
        "class NoteDetailDto(BaseModel):",
        "class FolderDto(BaseModel):",
        "class TagDto(BaseModel):",
        "class AssetDto(BaseModel):",
        "class FolderCreateRequestDto(BaseModel):",
        "class FolderUpdateRequestDto(BaseModel):",
        "class NoteSaveRequestDto(BaseModel):",
        "items: list[ItemT]",
        "total: int = Field(ge=0)",
        "limit: int = Field(ge=0)",
        "offset: int = Field(ge=0)",
        "tags: list[TagRefDto]",
        "folder_id: UUID | None = None",
        "score: float | None = None",
        "processing_error: str | None = None",
        "processing_warnings: list[dict[str, Any]]",
        "index_version: int = Field(ge=0)",
        "notes_count: int | None = Field(default=None, ge=0)",
        "size_bytes: int = Field(ge=0)",
        "tags: list[str] = Field(default_factory=list)",
        'model_config = ConfigDict(extra="forbid")',
    ]

    for fragment in expected_fragments:
        assert fragment in dto_source
