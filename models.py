from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field



class SDSGlobalDatabase(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    sds_pdf_product_name: str = Field(serialization_alias="product_name")
    sds_pdf_manufacture_name: str = Field(serialization_alias="manufacturer_name")
    sds_pdf_revision_date: str = Field(serialization_alias="revision_date")
    language: str = Field(serialization_alias="language_name")
    regulation_area: Optional[str] = None
    cas_no: Optional[str] = None
    link_to_public_view: str = Field(serialization_alias="file_url")
    product_code: Optional[str] = None
    version: Optional[str] = None
    related_locations: List[str] = Field(default_factory=list)
    language_code: str


class Location(BaseModel):
    id: int
    name: str


class Icon(BaseModel):
    url: str
    description: str
    type: str


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
    code: str
    name: str


class Regulation(BaseModel):
    model_config = {"extra": "ignore"}
    url: Optional[str] = None
    json_data: Dict[str, Any] = Field(default_factory=dict, alias="json")
    ec_no: Optional[str] = None
    cas_no: Optional[str] = None
    listing: Optional[str] = None
    listing_url: Optional[str] = None
    chemical_name: Optional[str] = None
    listing_short_desc: Optional[str] = None


class HazardCode(BaseModel):
    id: int
    edited: bool
    statements: str
    statement_code: str


class PrecautionaryCode(BaseModel):
    id: int
    edited: bool
    statements: str
    statement_code: str


class SDSChemical(BaseModel):
    model_config = {"extra": "ignore"}
    ec_no: Optional[str] = None
    cas_no: str
    conc_no: str
    conc_to: Optional[float] = None
    reach_no: Optional[str] = None
    conc_from: Optional[float] = None
    chemical_name: str
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
    language: Language
    revision: Optional[str] = None
    upc_code: Optional[str] = None
    euh_codes: List[Any] = Field(default_factory=list)
    telephone: Optional[str] = None
    components: Optional[str] = None
    issue_date: Optional[str] = None
    trade_name: Optional[str] = None
    health_risk: Optional[int] = None
    master_date: Optional[str] = None
    regulations: List[Regulation] = Field(default_factory=list)
    safety_risk: Optional[int] = None
    signal_word: Optional[str] = None
    hazard_codes: List[HazardCode] = Field(default_factory=list)
    intented_use: Optional[str] = None
    is_hazardous: bool
    printed_date: Optional[str] = None
    product_code: Optional[str] = None
    reach_reg_no: Optional[str] = None
    sds_chemical: List[SDSChemical] = Field(default_factory=list)
    chemical_name: Optional[str] = None
    ec_components: Optional[str] = None
    material_name: Optional[str] = None
    product_group: Optional[str] = None
    purchase_year: Optional[str] = None
    revision_date: Optional[str] = None
    english_sdspdf: bool
    published_date: Optional[str] = None
    substance_name: Optional[str] = None
    chemical_family: Optional[str] = None
    chemical_formula: Optional[str] = None
    company_web_site: Optional[str] = None
    environment_risk: Optional[int] = None
    hazard_statement: Optional[str] = None
    signal_word_code: Optional[str] = None
    recompute_version: List[str] = Field(default_factory=list)
    external_system_id: Optional[str] = None
    ghs_pictogram_code: Optional[str] = None
    product_identifier: Optional[str] = None
    newer_revision_date: Optional[str] = None
    precautionary_codes: List[PrecautionaryCode] = Field(default_factory=list)
    private_regulations: List[Any] = Field(default_factory=list)
    sds_pdf_product_name: Optional[str] = None
    used_advised_against: Optional[str] = None
    is_hazardous_chemical: bool
    chemical_name_synonyms: Optional[str] = None
    private_regulation_ids: List[Any] = Field(default_factory=list)
    regulation_listing_ids: List[int] = Field(default_factory=list)
    company_name_distributor: Optional[str] = None
    sds_pdf_manufacture_name: Optional[str] = None
    company_name_supplier_sds: Optional[str] = None
    manufacturer_company_name: Optional[str] = None
    emergency_telephone_number: Optional[str] = None
    producer_of_sds_company_name: Optional[str] = None
    hazard_category_abbreviations: Optional[str] = None
    private_regulation_listing_ids: List[Any] = Field(default_factory=list)


class SDSOtherInfoItem(BaseModel):
    tag: str
    value: str
    default_literal: str
    no_data_available: bool


class SubstanceDetail(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    is_archived: bool
    sds_id: int
    public_view_url: str = Field(serialization_alias="file_url")
    safety_summary_url: str = Field(serialization_alias="safety_summary_url")
    language: str
    product_name: str
    supplier_name: str
    product_code: str
    revision_date: str
    created_date: str
    ean_code: Optional[str] = None
    upc_code: Optional[str] = None
    external_system_id: Optional[str] = None
    external_system_url: Optional[str] = None
    hazard_sentences: str
    euh_sentences: str
    prevention_sentences: str
    location: Location
    substance_amount: Optional[str] = None
    substance_approval: Optional[str] = None
    nfpa: Optional[str] = None
    hmis: Optional[str] = None
    icons: List[Icon] = Field(default_factory=list)
    highest_risks: HighestRisks
    highest_storage_risks: HighestStorageRisks
    # info_msg: Optional[str] = None
    # attachments: List[Any] = Field(default_factory=list)
    sds_info: SDSInfo
    sds_other_info: Dict[str, List[SDSOtherInfoItem]] = Field(default_factory=dict)

class SDSRequest(BaseModel):
    model_config = {"extra": "ignore"}
    id: int
    product_name: Optional[str] = Field(serialization_alias="product_name")
    supplier_name: Optional[str] = Field(serialization_alias="manufacturer_name")
    product_code: Optional[str] = Field(serialization_alias="product_code")
    revision_date: str = Field(serialization_alias="revision_date")
    language: Optional[str] = Field(serialization_alias="language_name")
    created_date: str
    department: Optional[dict] = Field(serialization_alias="department")

class PaginatedResponse(BaseModel):
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[Any] = Field(default_factory=list)

class SubstanceListApiResponse(PaginatedResponse):
    results: List[SubstanceDetail] = Field(default_factory=list)
    

class FileInfo(BaseModel):
    model_config = {"extra": "ignore"}
    
    step: str
    progress: int
    file_name: str
    file_path: str

class BookletInfo(BaseModel):
    model_config = {"extra": "ignore"}
    
    booklet_id: int
    booklet_view_url: str = Field(serialization_alias="file_url")

class GetExtractionStatusApiResponse(BaseModel):
    model_config = {"extra": "ignore"}
    
    email: str
    request_id: str
    step: str
    progress: int
    file_info: Optional[Dict[str, FileInfo]] = Field(default_factory=dict)
    compression_file_info: Optional[Dict[str, Any]] = Field(default_factory=dict)
    init_time: str
    booklet_info: Optional[Dict[str, BookletInfo]] = Field(default_factory=dict)



class SearchGlobalDatabaseResponse(BaseModel):
    model_config = {"extra": "ignore"}
    results: List[SDSGlobalDatabase] = Field(default_factory=list)
    count: int
    next: Optional[str] = None
    previous: Optional[str] = None