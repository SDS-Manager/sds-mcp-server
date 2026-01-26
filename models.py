from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class LimitsResponse(BaseModel):
    chat_agent_search_limit: int = Field(serialization_alias="global_search_sds_limit")
    chat_agent_get_sds_limit: int = Field(serialization_alias="show_sds_detail_limit")
    chat_agent_search_count: int = Field(serialization_alias="global_search_sds_used")
    chat_agent_get_sds_count: int = Field(serialization_alias="show_sds_detail_used")


class StatisticsResponse(BaseModel):
    products_count: int
    request_count: int
    sds_count: int
    locations_count: int


class PaginatedResponse(BaseModel):
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[Any] = Field(default_factory=list)


class GlobalSdsSearch(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    sds_pdf_product_name: str = Field(serialization_alias="product_name")
    producer_name: str = Field(serialization_alias="supplier_name")
    sds_pdf_revision_date: Optional[str] = Field(serialization_alias="revision_date")
    language: Optional[str] = Field(serialization_alias="language_name")
    language_code: Optional[str]
    regulation_area: Optional[str] = None
    cas_no: Optional[str] = None
    link_to_public_view: Optional[str] = Field(serialization_alias="file_url")
    product_code: Optional[str] = None
    version: Optional[str] = None
    related_locations: Optional[List[str]] = Field(default_factory=list)


class SearchGlobalDatabaseResponse(PaginatedResponse):
    results: List[GlobalSdsSearch] = Field(default_factory=list)


class ImportProductListResponse(BaseModel):
    id: int
    name: str
    wish_list_file: str = Field(serialization_alias="file")
    uploaded_by: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="uploaded_by")


class GetImportProductListResponse(PaginatedResponse):
    results: List[ImportProductListResponse] = Field(default_factory=list)


class ProductListSummaryResponse(BaseModel):
    id: int
    product_name: str
    supplier_name: Optional[str] = None
    department: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="department")
    language: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="language")
    linked_sds: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="linked_sds")
    external_system_id: Optional[str] = None
    matched: Optional[bool] = None
    is_deleted: Optional[bool] = None


class GetProductListSummaryResponse(PaginatedResponse):
    results: List[ProductListSummaryResponse] = Field(default_factory=list)


class Location(BaseModel):
    id: int
    name: str


class Icon(BaseModel):
    url: Optional[str]
    description: Optional[str]
    type: Optional[str]


class HighestRisks(BaseModel):
    health_risk: Optional[int] = None
    safety_risk: Optional[int] = None
    environment_risk: Optional[int] = None
    health_risk_incl_ppe: Optional[int] = None
    safety_risk_incl_ppe: Optional[int] = None
    environment_risk_incl_ppe: Optional[int] = None


class HighestStorageRisks(BaseModel):
    storage_safety_risk: Optional[int] = None
    storage_environment_risk: Optional[int] = None


class Language(BaseModel):
    id: int
    code: Optional[str]
    name: Optional[str]


class Regulation(BaseModel):
    model_config = {"extra": "ignore"}
    url: Optional[str] = None
    json_data: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="json")
    ec_no: Optional[str] = None
    cas_no: Optional[str] = None
    listing: Optional[str] = None
    listing_url: Optional[str] = None
    chemical_name: Optional[str] = None
    listing_short_desc: Optional[str] = None


class HazardCode(BaseModel):
    id: int
    edited: Optional[bool]
    statements: Optional[str]
    statement_code: Optional[str]


class PrecautionaryCode(BaseModel):
    id: int
    edited: Optional[bool]
    statements: Optional[str]
    statement_code: Optional[str]


class SDSChemical(BaseModel):
    model_config = {"extra": "ignore"}
    ec_no: Optional[str] = None
    cas_no: Optional[str]
    conc_no: Optional[str]
    conc_to: Optional[float] = None
    reach_no: Optional[str] = None
    conc_from: Optional[float] = None
    chemical_name: Optional[str]
    name_from_library: Optional[bool] = None
    raw_chemical_name: Optional[str] = None
    hazards_statements: Optional[str] = None


class SDSInfo(BaseModel):
    model_config = {"extra": "ignore"}
    uuid: Optional[str] = None
    ec_no: Optional[str] = None
    email: Optional[str] = None
    cas_no: Optional[str] = None
    einecs: Optional[str] = None
    sds_no: Optional[str] = None
    ufi_no: Optional[str] = None
    address: Optional[str] = None
    version: Optional[str] = None
    ean_code: Optional[str] = None
    iso_icon: Optional[str] = None
    language: Optional[Language] = None
    revision: Optional[str] = None
    upc_code: Optional[str] = None
    euh_codes: Optional[List[Any]] = Field(default_factory=list)
    telephone: Optional[str] = None
    components: Optional[str] = None
    issue_date: Optional[str] = None
    trade_name: Optional[str] = None
    health_risk: Optional[int] = None
    master_date: Optional[str] = None
    regulations: Optional[List[Regulation]] = Field(default_factory=list)
    safety_risk: Optional[int] = None
    signal_word: Optional[str] = None
    hazard_codes: Optional[List[HazardCode]] = Field(default_factory=list)
    intented_use: Optional[str] = None
    is_hazardous: Optional[bool]
    printed_date: Optional[str] = None
    product_code: Optional[str] = None
    reach_reg_no: Optional[str] = None
    sds_chemical: Optional[List[SDSChemical]] = Field(default_factory=list)
    chemical_name: Optional[str] = None
    ec_components: Optional[str] = None
    material_name: Optional[str] = None
    product_group: Optional[str] = None
    purchase_year: Optional[str] = None
    revision_date: Optional[str] = None
    english_sdspdf: Optional[bool]
    published_date: Optional[str] = None
    substance_name: Optional[str] = None
    chemical_family: Optional[str] = None
    chemical_formula: Optional[str] = None
    company_web_site: Optional[str] = None
    environment_risk: Optional[int] = None
    hazard_statement: Optional[str] = None
    signal_word_code: Optional[str] = None
    external_system_id: Optional[str] = None
    ghs_pictogram_code: Optional[str] = None
    product_identifier: Optional[str] = None
    newer_revision_date: Optional[str] = None
    precautionary_codes: Optional[List[PrecautionaryCode]] = Field(default_factory=list)
    private_regulations: Optional[List[Any]] = Field(default_factory=list)
    sds_pdf_product_name: Optional[str] = None
    used_advised_against: Optional[str] = None
    is_hazardous_chemical: Optional[bool]
    chemical_name_synonyms: Optional[str] = None
    private_regulation_ids: Optional[List[Any]] = Field(default_factory=list)
    regulation_listing_ids: Optional[List[int]] = Field(default_factory=list)
    company_name_distributor: Optional[str] = None
    sds_pdf_manufacture_name: Optional[str] = None
    company_name_supplier_sds: Optional[str] = None
    manufacturer_company_name: Optional[str] = None
    emergency_telephone_number: Optional[str] = None
    producer_of_sds_company_name: Optional[str] = None
    hazard_category_abbreviations: Optional[str] = None
    private_regulation_listing_ids: Optional[List[Any]] = Field(default_factory=list)


class SDSOtherInfoItem(BaseModel):
    tag: str
    value: Optional[str]
    default_literal: Optional[str]
    no_data_available: Optional[bool]


class SubstanceDetail(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    is_archived: Optional[bool]
    sds_id: Optional[int]
    public_view_url: Optional[str] = Field(serialization_alias="file_url")
    safety_summary_url: Optional[str] = Field(serialization_alias="safety_summary_url")
    language: Optional[str]
    product_name: Optional[str]
    supplier_name: Optional[str]
    product_code: Optional[str]
    revision_date: Optional[str]
    created_date: Optional[str]
    ean_code: Optional[str] = None
    upc_code: Optional[str] = None
    external_system_id: Optional[str] = None
    external_system_url: Optional[str] = None
    hazard_sentences: Optional[str]
    euh_sentences: Optional[str]
    prevention_sentences: Optional[str]
    location: Optional[Location] = None
    substance_amount: Optional[str] = None
    substance_approval: Optional[str] = None
    nfpa: Optional[str] = None
    hmis: Optional[str] = None
    icons: Optional[List[Icon]] = Field(default_factory=list)
    highest_risks: Optional[HighestRisks] = None
    highest_storage_risks: Optional[HighestStorageRisks] = None
    # info_msg: Optional[str] = None
    # attachments: List[Any] = Field(default_factory=list)
    sds_info: Optional[SDSInfo] = None
    sds_other_info: Optional[Dict[str, List[SDSOtherInfoItem]]] = Field(default_factory=dict)


class SDSRequest(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    product_name: str
    supplier_name: str
    product_code: Optional[str]
    revision_date: Optional[str]
    language: Optional[str] = Field(serialization_alias="language_name")
    created_date: Optional[str]
    department: Optional[dict]
    created_by: Optional[dict]


class SdsRequestResponse(PaginatedResponse):
    results: List[SDSRequest] = Field(default_factory=list)


class SubstanceListApiResponse(PaginatedResponse):
    results: List[SubstanceDetail] = Field(default_factory=list)
    

class FileInfo(BaseModel):
    model_config = {"extra": "ignore"}
    
    step: str
    progress: int
    file_name: str
    file_path: Optional[str]


class BookletInfo(BaseModel):
    model_config = {"extra": "ignore"}
    
    booklet_id: int
    booklet_view_url: Optional[str] = Field(serialization_alias="file_url")


class GetExtractionStatusApiResponse(BaseModel):
    model_config = {"extra": "ignore"}
    
    email: str
    request_id: str
    step: str
    progress: int
    file_info: Optional[Dict[str, FileInfo]] = Field(default_factory=dict)
    compression_file_info: Optional[Dict[str, Any]] = Field(default_factory=dict)
    init_time: Optional[str]
    booklet_info: Optional[Dict[str, BookletInfo]] = Field(
        default_factory=dict,
        serialization_alias="imported_info"
    )


class ActivityLog(BaseModel):
    model_config = {"extra": "ignore"}
    
    type: Literal["product_log", "location_log"]
    created_date: str
    updated_by: Optional[Dict[str, Any]] = Field(default_factory=dict)
    product_info: Optional[Dict[str, Any]] = Field(default_factory=dict)
    location_info: Optional[Dict[str, Any]] = Field(default_factory=dict)
    log: Optional[Dict[str, Any]] = Field(default_factory=dict)


class ActivityLogResponse(PaginatedResponse):
    results: List[ActivityLog] = Field(default_factory=list)
