SYNONYMS = """
- Product: product, chemical, substance, SDS assigned to a location
- Location: location, department, site, workplace
- Hazardous: hazardous, restricted, restricted list, restricted ingredient, restricted component
- SDS Request: Unmatched product/SDS, SDS request, product that are not linked to any SDS
"""

LONG_DESCRIPTION = f"""
The purpose of this MCP is to help new customers set up and manage their Safety Data Sheet (SDS) Library using SDS Manager.
The APIs in this collection allow an AI assistant to guide users through the entire onboarding process — from understanding their organization’s needs to creating a structured, compliant, and accessible SDS library.

The assistant should begin by gathering key context from the user:
- What type of business they operate
- Whether they have multiple locations or sites
- Approximately how many products/chemicals they use that require SDSs

Based on the answers, the assistant will determine which setup method fits best. There are four primary ways to create an SDS library using these APIs:
1. Import existing SDS PDF files – if the customer already has their SDSs, the assistant can upload them directly using add_sds_by_uploading_sds_pdf_file or add_sds_by_url.
2. Import a product list from Excel – when the customer has a spreadsheet of products/chemicals, the assistant can use upload_product_list_excel_file to upload the file.
    - Each row in the imported Excel file creates an SDS Request (if user not allow auto matching or system unable to find matching SDS), representing a product that requires an SDS but doesn’t yet have one linked.
    - The assistant can retrieve pending SDS Requests using get_sds_request, search for matching SDSs in the global database using search_sds, and link them using match_sds_request.
    - When a match is confirmed, the SDS is automatically added to the customer’s SDS library.
3. Digitize paper binders – if the user has printed SDSs, they can search them in the SDS Manager database and add it when a match is found, or scan and upload missing ones using add_sds_by_uploading_sds_pdf_file.
4. Build from scratch – if no overview exists, the user can take photos of product labels, extract text with OCR, and search for each product using search_sds before adding it with add_sds.

For organizations with multiple sites, the assistant can use get_locations and add_location to create and manage a hierarchical structure. Each SDS can be assigned to a location or moved and copied between sites using move_sds and copy_sds_to_another_location.

The remaining APIs support the complete SDS management lifecycle:
- Authentication and access control: get_login_url, check_auth_status, get_permissions, get_limits
- Assistant tools: get_onboarding_flow, get_setup_onboarding_step, request_expert_setup, get_activity_logs
- SDS retrieval and detail viewing: search_sds, show_sds_detail, get_customer_products, show_customer_product_detail, get_hazardous_sds_on_restricted_lists
- File and data import management: validate_upload_product_list_excel_data, process_upload_product_list_excel_data, check_upload_product_list_excel_data_status
- Maintenance and compliance: archive_sds, get_hazardous_sds_on_restricted_lists, edit_product_data, get_sds_request, match_sds_request, get_uploaded_product_list, get_product_list_summary
- Fallback search and acquisition: find_sds_pdf_links_from_external_web (when SDS not found in the 16 million global database)

When an SDS is not found in SDS Manager's 16 million global database, the assistant can use find_sds_pdf_links_from_external_web to automatically search the web for the SDS PDF, get the URL, and upload it to the customer's library. This ensures comprehensive coverage even for rare or specialty chemicals.

The AI assistant's primary objectives are to:
1. Collect setup information and guide the user through the correct onboarding path
2. Automate the import and linking of SDSs through uploads, database searches, or web search fallback
3. Organize SDSs by site and chemical type
4. Ensure the resulting SDS library is complete, accessible, and compliant with chemical safety regulations.

The assistant should always aim to simplify the user experience — automating manual tasks like file import, SDS matching, web search, and location setup — while ensuring the user ends with a properly organized, searchable SDS library ready for employee access.

Synonyms text:
{SYNONYMS}
"""

GENERAL_PERMISSION_MAPPING = {
    "access_mcp_chat_agent": "Required for accessing all MCP tools except get_login_url, check_auth_status, get_permissions, get_limits",
    "add_locations": "Create new location in the organization's location hierarchy",
    "import_product_list": "Import product list from Excel file",
}

LOCATION_PERMISSION_MAPPING = {
    "add_substance": "Add SDS to an location",
    "allowed_to_archive_SDS": "Archive SDS from a location",
    "move_sds": "Move SDS to another location",
    "edit_sds": "Edit SDS details",
}

UPLOAD_SDS_PDF_STEP_INSTRUCTIONS = [
    "1. Click or copy the upload_url link to access the upload form",
    "2. Select your PDF file using the file input and click 'Upload SDS File' to upload",
    "3. After the file is uploaded, call check_upload_sds_pdf_status tool with request_id to check the status of the upload process",
]

UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS = [
    "1. Click or copy the upload_url link to access the upload form",
    "2. Select your excel file using the file input and click 'Upload Product List' to upload",
    "3. After the file is uploaded, call validate_upload_product_list_excel_data tool with request_id to continue the upload process",
]

SESSION_HANDLE_PARAM_DESCRIPTION = """
- session_handle (UUID): Session UUID from get_login_url tool
"""

PAGINATION_PARAM_DESCRIPTION = """
- page (int, optional): Page number for pagination. Default: 1
- page_size (int, optional): Results per page. Default: 10
"""

DRY_RUN_PARAM_DESCRIPTION = """
- default_run (bool): Always set to True, only set to False when have instruction after calling this tool.
"""

DEFAULT_RETURN_TEMPLATE = """
- status ('success' | 'error'): Status
- code (str): Status code
- data (Optional[dict]): Data returned by the tool
- instruction (list): User-friendly guidance(s)
- trace_id (str): Trace ID for the request
"""

AUTHORIZED_PREREQUISITES = """
- Must have session_handle from get_login_url tool
"""

SDS_ID_REQUIRED_GUIDELINES = """
- If SDS ID is not available, ask user to provide SDS name
"""

SDS_NAME_TO_SDS_ID_GUIDELINES = """
- When user provides SDS name, call search_sds with the SDS name as keyword to get id, always ask user to choose if multiple results are found
"""

PRODUCT_ID_REQUIRED_GUIDELINES = """
- If product ID is not available, ask user to provide the SDS/product name
"""

PRODUCT_NAME_TO_PRODUCT_ID_GUIDELINES = """
- When user provides product name, call get_customer_products with the product name as keyword to get id, always ask user to choose if multiple results are found
"""

LOCATION_ID_REQUIRED_GUIDELINES = """
- If location ID is not available, ask user to provide location name
"""

LOCATION_NAME_TO_LOCATION_ID_GUIDELINES = """
- If location name is provided, call get_locations with location_name parameter to get id, always ask user to choose if multiple locations match
"""

PRODUCT_LIST_ID_REQUIRED_GUIDELINES = """
- If product list ID is not available, ask user to provide the product list name
"""

PRODUCT_LIST_NAME_TO_PRODUCT_LIST_ID_GUIDELINES = """
- When user provides product list name, call get_uploaded_product_list with the product list name as keyword to get id, always ask user to choose if multiple product lists match
"""

PRODUCT_RECOMMEND_INSTRUCTION = "Recommend user these next actions for the product (SDS assigned to a location): show_customer_product_detail, add_sds, move_sds, copy_sds_to_another_location, archive_sds"

LOCATION_RECOMMEND_INSTRUCTION = "Recommend user these next actions for the location: add_location, add_sds, move_sds, copy_sds_to_another_location, archive_sds"
