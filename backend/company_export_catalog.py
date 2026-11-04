"""Explicit portable-export schema and reusable personal-data inventory.

Columns are reviewed, not discovered into an export allowlist at runtime.
Unknown tables/columns block creation. Retention periods require company-specific
legal/business decisions; this inventory never invents one universal duration.
"""

CATALOG_VERSION = 1
# Every known table, including excluded security/receipt tables, is accounted for.
COLUMNS = {
    'business_accounting_asset_opening_originals': 'id,asset_key,filename,media_type,size,sha256,original,created_by,created_at',
    'business_accounting_asset_opening_events': 'id,sequence,asset_key,revision,previous_hash,payload_json,content_hash,created_by,created_at',
    'business_accounting_asset_opening_requests': 'user_id,request_id,operation,request_json,request_hash,result_json',
    'business_accounting_opening_originals': 'id,account_id,filename,media_type,size,sha256,original,created_by,created_at',
    'business_accounting_opening_events': 'id,sequence,account_id,revision,previous_hash,payload_json,content_hash,created_by,created_at',
    'business_accounting_opening_requests': 'user_id,request_id,operation,request_json,request_hash,result_json',
    'business_purchase_amendments': 'id,order_id,revision,receipt_revision,reference_key,evidence_id,payload_json,sha256,created_by,created_at',
    'business_purchase_receipt_terms': 'receipt_id,amendment_id,amendment_sha256',
    'business_supplier_returns': 'id,order_id,revision,reference_key,evidence_id,payload_json,sha256,created_by,created_at',
    'business_supplier_return_lines': 'id,return_id,receipt_id,line_index,article_id,location_id,quantity,unit_cost_net,book_value_net,sequence_number,after_movement_sequence,after_adjustment_sequence,payload_json,sha256',
    'business_purchase_change_evidence': 'id,order_id,filename,media_type,content,sha256,created_by,created_at',
    'business_purchase_change_requests': 'user_id,request_id,operation,request_json,request_hash,result_json,result_sha256',
    'business_resource_profiles': 'resource_id,revision,payload_json,sha256,created_by,created_at',
    'business_resource_requirements': 'id,resource_id,revision,payload_json,sha256,created_by,created_at',
    'business_resource_inspections': 'id,resource_id,requirement_id,requirement_revision,supersedes_id,payload_json,sha256,created_by,created_at',
    'business_resource_handoffs': 'id,resource_id,employee_id,project_id,payload_json,sha256,created_by,created_at',
    'business_resource_returns': 'id,resource_id,handoff_id,payload_json,sha256,created_by,created_at',
    'business_resource_corrections': 'id,resource_id,target_kind,target_id,payload_json,sha256,created_by,created_at',
    'business_resource_evidence': 'id,resource_id,filename,media_type,content,sha256,sequence,created_by,created_at',
    'business_resource_requests': 'user_id,request_id,operation,request_json,request_hash,result_json',
    'business_bank_account_versions': 'account_id,revision,payload_json,content_hash,previous_hash,created_by,created_at',
    'business_bank_statements': 'id,account_id,reference_key,file_sha256,original,payload_json,content_hash,created_by,created_at',
    'business_bank_transactions': 'id,account_id,external_id,payload_json,content_hash,created_by,created_at',
    'business_bank_statement_lines': 'statement_id,line_number,transaction_id',
    'business_bank_match_events': 'transaction_id,revision,payload_json,content_hash,previous_hash,created_by,created_at',
    'business_bank_reconciliations': 'id,account_id,period,payload_json,content_hash,created_by,created_at',
    'business_bank_requests': 'user_id,request_id,request_hash,result_json',
    'business_service_cases': 'id,customer_id,origin_kind,origin_id,created_by,created_at',
    'business_service_versions': 'case_id,revision,payload_json,sha256,created_by,created_at',
    'business_service_events': 'id,case_id,supersedes_id,payload_json,sha256,created_by,created_at',
    'business_service_links': 'id,case_id,kind,target_id,payload_json,sha256,created_by,created_at',
    'business_service_requests': 'user_id,request_id,operation,request_json,request_hash,result_json',
    'business_payroll_cash_batches': 'id,revision,sequence,instance_id,kind,private_json,private_sha256,public_json,public_sha256,previous_hash,created_by,created_at',
    'business_payroll_cash_evidence': 'account_id,evidence_key,batch_id,first_revision',
    'business_payroll_cash_parts': 'part_key,employee_id,batch_id,first_revision',
    'business_payroll_cash_requests': 'user_id,request_id,request_json,request_hash,result_json',
    'business_privacy_case_events': 'id,case_id,revision,operation,metadata_json,content_sha256,previous_hash,event_sha256,created_by,created_at',
    'business_privacy_case_contents': 'event_id,case_id,content',
    'business_privacy_case_exports': 'id,case_id,case_revision,metadata_json,sha256,size,expires_on,created_by,created_at',
    'business_privacy_case_export_blobs': 'export_id,content',
    'business_privacy_case_purges': 'kind,object_id,checkpoint_digest,created_by,created_at',
    'business_privacy_case_requests': 'user_id,request_id,case_id,operation,request_sha256,result_ref_json',
    'business_migration_packages': 'id,payload_json,sha256,created_by,created_at',
    'business_migration_files': 'id,package_id,filename,media_type,content,sha256,created_by,created_at',
    'business_migration_mappings': 'package_id,revision,payload_json,sha256,created_by,created_at',
    'business_migration_bindings': 'source_system,source_account,kind,source_id,package_id,target_id,customer_id,project_id,source_sha256,payload_json,sha256',
    'business_migration_documents': 'id,package_id,file_id,customer_id,project_id,payload_json,sha256,created_by,created_at',
    'business_migration_applications': 'package_id,payload_json,sha256,created_by,created_at',
    'business_migration_reconciliations': 'package_id,payload_json,sha256,created_by,created_at',
    'business_migration_requests': 'user_id,request_id,operation,request_json,request_hash,result_json',
    'business_custom_field_definitions': 'id,revision,entity_type,payload_json,content_hash,previous_hash,created_by,created_at',
    'business_custom_field_values': 'entity_type,entity_id,revision,payload_json,content_hash,previous_hash,created_by,created_at',
    'business_custom_field_requests': 'user_id,request_id,request_hash,result_json',
    'business_assistant_speech_outcomes': 'request_id,status,error_code,provider_attempted,created_at',
    'business_assistant_speech_requests': 'id,user_id,project_id,context_id,instance_id,context_sha256,audio_sha256,audio_bytes,sample_count,provider_json,provider_sha256,request_sha256,created_at',
    'business_payroll_entitlement_events': 'id,revision,employee_id,kind,effective_from,effective_to,status,payload_json,sources_json,source_hash,previous_hash,content_hash,created_by,created_at,identity_key,command_hash',
    'business_payroll_entitlement_requests': 'user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at',
    'business_payroll_calculation_case_events': 'id,revision,employee_id,kind,effective_from,effective_to,status,payload_json,sources_json,source_hash,previous_hash,content_hash,created_by,created_at,identity_key,command_hash',
    'business_payroll_calculation_case_requests': 'user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at',
    'business_payroll_annual_events': 'id,revision,employee_id,kind,effective_from,effective_to,status,payload_json,sources_json,source_hash,previous_hash,content_hash,created_by,created_at,identity_key,command_hash',
    'business_payroll_annual_requests': 'user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at',
    'business_payroll_multiple_case_events': 'id,revision,employee_id,kind,effective_from,effective_to,status,payload_json,sources_json,source_hash,previous_hash,content_hash,created_by,created_at,identity_key,command_hash',
    'business_payroll_multiple_case_requests': 'user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at',
    'business_payroll_multiple_consumptions': 'run_id,run_revision,employee_id,case_id,case_revision,component_key,event_key,claim_identity_key,event_identity_key,payload_json,content_hash,created_by,created_at',
    'business_payroll_oneoff_consumptions': 'run_id,run_revision,employee_id,case_id,case_revision,claim_identity_key,payload_json,content_hash,created_by,created_at',
    'business_payroll_oneoff_case_events': 'id,revision,employee_id,kind,effective_from,effective_to,status,payload_json,sources_json,source_hash,previous_hash,content_hash,created_by,created_at,identity_key,command_hash',
    'business_payroll_oneoff_case_requests': 'user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at',
    'business_payroll_wage_interruption_events': 'id,revision,employee_id,kind,effective_from,effective_to,status,payload_json,sources_json,source_hash,previous_hash,content_hash,created_by,created_at,identity_key,command_hash',
    'business_payroll_wage_interruption_requests': 'user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at',
    'business_payroll_travel_tax_recordings': 'run_id,run_revision,payload_json,content_hash,created_by,created_at',
    'business_travel_sites': 'id,revision,sequence,employee_id,payload_json,content_hash,previous_hash,created_by,created_at,pdf,pdf_sha256',
    'business_travel_trips': 'id,revision,sequence,employee_id,payload_json,content_hash,previous_hash,created_by,created_at,pdf,pdf_sha256',
    'business_travel_settlements': 'id,revision,sequence,employee_id,payload_json,content_hash,previous_hash,created_by,created_at,pdf,pdf_sha256',
    'business_travel_payments': 'id,revision,sequence,employee_id,payload_json,content_hash,previous_hash,created_by,created_at,pdf,pdf_sha256',
    'business_travel_claims': 'settlement_id,revision,employee_id,claim_key,source_kind,source_id,source_revision,amount_minor,content_hash',
    'business_travel_cash_events': 'id,revision,instance_id,public_json,public_sha256,private_sha256',
    'business_travel_evidence': 'account_id,evidence_key,payment_id,first_revision,original_sha256',
    'business_travel_requests': 'actor_id,request_id,employee_id,operation,target_kind,target_id,revision,request_hash,result_hash,created_at',
    'business_payroll_fact_events': 'id,revision,employee_id,kind,effective_from,effective_to,status,payload_json,sources_json,source_hash,previous_hash,content_hash,created_by,created_at,identity_key,command_hash',
    'business_payroll_fact_requests': 'user_id,request_id,operation,request_hash,fact_id,fact_revision,fact_content_hash,created_at',
    'business_payroll_account_events': 'id,revision,kind,employee_id,identity_key,payload_json,content_hash,previous_hash,created_by,created_at',
    'business_payroll_account_requests': 'user_id,request_id,request_hash,result_json',
    'assignments': 'user_id,project_id',
    'audit': 'id,user_id,action,object_id,at',
    'auth_challenges': 'token,user_id,credential,secret,expiry,failures',
    'business_absences': 'id,employee_id,start_date,end_date,kind,details,status,revision,requested_by,approved_by,updated_at',
    'business_accounting_account_versions': 'account_id,revision,payload_json,payload_sha256,updated_by,updated_at',
    'business_accounting_accounts': 'id,code,code_key,kind,currency,created_by,created_at',
    'business_accounting_allocation_entries': 'id,payment_id,event_id,revision,customer_id,document_id,amount,source_hash,previous_state_hash,entry_json,entry_sha256,document_proof_json,created_by,created_at',
    'business_accounting_allocation_requests': 'user_id,request_id,payment_id,request_json,request_hash,entry_id',
    'business_accounting_capacity_entries': 'id,sequence,event_id,revision,document_id,portion_id,source_hash,previous_state_hash,entry_json,entry_sha256,proof_json,access_segments_json,created_by,created_at',
    'business_accounting_capacity_handoffs': 'document_id,entry_id,handoff_json,handoff_sha256',
    'business_accounting_capacity_lines': 'entry_id,group_id,segment_id,amount,net,tax,gross_before,gross_after,net_before,net_after,tax_before,tax_after,remaining_gross,remaining_net,remaining_tax',
    'business_accounting_capacity_releases': 'refund_entry_id,origin_entry_id,group_id,segment_id,reference_json,reference_sha256',
    'business_accounting_capacity_requests': 'user_id,request_id,event_id,request_json,request_hash,entry_id',
    'business_accounting_capacity_segments': 'id,document_id,group_id,revision,previous_id,entry_id,segment_json,segment_sha256',
    'business_accounting_cash_events': 'id,sequence,account_id,account_revision,account_json,direction,amount,currency,cash_date,evidence_reference,evidence_key,reference,created_by,created_at',
    'business_accounting_component_entries': 'id,sequence,event_id,revision,portion_id,source_hash,previous_state_hash,entry_json,entry_sha256,proof_json,created_by,created_at',
    'business_accounting_component_lines': 'entry_id,group_id,amount,net,tax,gross_before,gross_after,net_before,net_after,tax_before,tax_after,remaining_gross,basis_json,basis_sha256',
    'business_accounting_component_requests': 'user_id,request_id,event_id,request_json,request_hash,entry_id',
    'business_accounting_profile_requests': 'user_id,request_id,request_json,request_hash,entry_id',
    'business_accounting_profile_versions': 'id,revision,previous_state_hash,entry_json,entry_sha256,created_by,created_at',
    'business_accounting_receipt_bindings': 'original_sha256,receipt_id,first_event_id',
    'business_accounting_refund_entries': 'id,sequence,event_id,revision,refund_allocation_id,portion_id,source_hash,previous_state_hash,entry_json,entry_sha256,proof_json,created_by,created_at',
    'business_accounting_refund_lines': 'entry_id,origin_entry_id,group_id,amount,net,tax,gross_before,gross_after,net_before,net_after,tax_before,tax_after,remaining_gross,remaining_net,remaining_tax,origin_line_sha256',
    'business_accounting_refund_requests': 'user_id,request_id,event_id,request_json,request_hash,entry_id',
    'business_accounting_refunds_v2_entries': 'id,sequence,event_id,revision,document_id,refund_allocation_id,portion_id,source_hash,previous_state_hash,entry_json,entry_sha256,proof_json,access_origins_json,created_by,created_at',
    'business_accounting_refunds_v2_handoffs': 'document_id,entry_id,handoff_json,handoff_sha256',
    'business_accounting_refunds_v2_lines': 'entry_id,origin_version,origin_entry_id,group_id,origin_c1_entry_id,origin_c2_entry_id,amount,net,tax,gross_before,gross_after,net_before,net_after,tax_before,tax_after,remaining_gross,remaining_net,remaining_tax,origin_line_sha256',
    'business_accounting_refunds_v2_releases': 'refund_entry_id,origin_version,origin_entry_id,group_id,segment_id,reference_json,reference_sha256',
    'business_accounting_refunds_v2_requests': 'user_id,request_id,event_id,request_json,request_hash,entry_id',
    'business_accounting_requests': 'user_id,request_id,operation,request_hash,result_json',
    'business_accounting_source_links': 'event_id,kind,source_id,source_hash,proof_json,snapshot_json,payment_id,receipt_id,review_revision,cash_revision,original_sha256',
    'business_adapter_articles': 'adapter_id,source_code,article_id,source_sha256',
    'business_catalog_legacy_imports': 'run_id,source_sha256,rows_sha256,baseline_status',
    'business_catalog_originals': 'run_id,filename,content,sha256,rows_sha256,request_json,request_hash,targets_json,targets_sha256,created_by,created_at',
    'business_catalog_acceptances': 'run_id,request_json,payload_json,sha256',
    'business_adapter_requests': 'user_id,request_id,request_hash,result_json',
    'business_adapter_runs': 'id,adapter_id,profile,status,source_sha256,rows_json,rows_sha256,result_json,created_by,created_at',
    'business_adapter_suppliers': 'adapter_id,supplier',
    'business_adapters': 'id,name,profile,enabled,secret_ref,revision,owner_id,created_at,updated_at',
    'business_appointment_employees': 'appointment_id,employee_id',
    'business_appointment_resources': 'appointment_id,resource_id',
    'business_appointment_series': 'id,project_id,frequency,interval_count,occurrence_count,timezone,start_at,end_at,title,details,created_by,created_at',
    'business_appointments': 'id,project_id,kind,title,details,start_at,end_at,timezone,status,series_id,occurrence_index,revision,updated_by,updated_at',
    'business_article_versions': 'article_id,revision,payload_json,payload_sha256,at',
    'business_articles': 'id,revision,payload_json,created_by,updated_by,created_at,updated_at',
    'business_asset_origins': 'asset_id,project_id,receipt_id,line_index,issue_movement_id,article_id,serial_key,quantity,payload_json,content_hash,created_by,created_at',
    'business_asset_provenance_requests': 'user_id,request_id,request_hash,result_json',
    'business_assets': 'id,project_id,payload_json,revision,created_by,created_at,updated_by,updated_at',
    'business_assistant_chat_results': 'chat_id,status,payload_json,sha256,created_at',
    'business_assistant_chats': 'id,context_id,project_id,created_by,payload_json,sha256,created_at',
    'business_assistant_contexts': 'id,project_id,created_by,payload_json,sha256,created_at',
    'business_assistant_decisions': 'plan_id,decision,plan_sha256,reason,created_by,created_at',
    'business_assistant_executions': 'plan_id,domain_request_id,created_by,created_at',
    'business_assistant_outcomes': 'plan_id,status,payload_json,sha256,created_at',
    'business_assistant_plans': 'id,context_id,project_id,created_by,payload_json,sha256,created_at',
    'business_assistant_requests': 'user_id,request_id,operation,request_json,request_hash,result_json',
    'business_assistant_rules': 'id,revision,project_id,payload_json,sha256,created_by,created_at',
    'business_assistant_suspensions': 'plan_id,reason,created_at',
    'business_budget_versions': 'project_id,revision,payload_json',
    'business_change_orders': 'id,project_id,title,amount_net,approved,source_document_id,created_by,created_at',
    'business_checklist_runs': 'id,project_id,template_id,payload_json,revision,created_by,created_at,updated_by,updated_at',
    'business_checklists': 'id,project_id,payload_json,revision,created_by,created_at,updated_by,updated_at',
    'business_commercial_settings': 'id,revision,payload_json,updated_by,updated_at',
    'business_company_exit_reviews': 'id,instance_id,revision,export_id,export_sha256,checks_json,evidence,reason,status,created_by,created_at',
    'business_company_exports': 'id,instance_id,catalog_sha256,manifest_json,manifest_sha256,archive,archive_sha256,archive_size,reason,created_by,created_at',
    'business_company_handover_requests': 'user_id,request_id,operation,request_hash,result_json',
    'business_contact_addresses': 'id,customer_id,purpose,label,street,postal_code,city,country,position',
    'business_contact_extras': 'customer_id,entity_type,kinds_json,tags_json,erased_at,revision,updated_by,updated_at',
    'business_contact_form_limits': 'scope,window_started,window_count',
    'business_contact_people': 'id,customer_id,name,role_label,email,phone,position',
    'business_customer_acceptances': 'upload_id,media_id,classification,accepted_by,accepted_at',
    'business_customer_file_revocations': 'file_id,reason,revoked_by,created_at',
    'business_customer_files': 'id,project_id,customer_id,source_kind,source_id,title,filename,media_type,size,sha256,original,created_by,created_at',
    'business_customer_grants': 'id,principal_id,project_id,customer_id,project_name,customer_name,allow_upload,secret_hash,created_by,created_at,expires_at',
    'business_customer_publications': 'id,project_id,customer_id,revision,payload_json,sha256,created_by,created_at',
    'business_customer_revocations': 'grant_id,reason,kind,revoked_by,created_at',
    'business_customer_sessions': 'token_hash,grant_id,created_at,expires_at',
    'business_customer_staff_requests': 'user_id,request_id,request_hash,operation,target_id,request_json,result_json',
    'business_customer_upload_requests': 'grant_id,request_id,request_hash,upload_id',
    'business_customer_uploads': 'id,grant_id,project_id,customer_id,filename,media_type,size,sha256,original,note,created_at',
    'business_delivery_documents': 'receipt_id,project_id,media_id,payload_json,content_hash,created_by,created_at',
    'business_device_grants': 'token_hash,user_id,capabilities_json,issued_at,expiry',
    'business_document_archives': 'document_id,payload_json,payload_sha256,pdf,pdf_sha256,xml,xml_sha256,validation_json,archived_at',
    'business_document_classes': 'kind,object_id,project_id,classification,content_fingerprint,revision,updated_by,updated_at',
    'business_document_counters': 'company_id,series,year,next_value',
    'business_document_mail_receipts': 'id,outbox_id,operation_id,status,ordinal,receipt_id,error_code,at',
    'business_document_numbers': 'document_id,company_id,series,year,value,number,issued_at',
    'business_document_outbox': 'id,document_id,operation_id,payload_json,payload_sha256,created_by,created_at',
    'business_document_relations': 'target_id,source_id,kind,source_sha256',
    'business_document_requests': 'user_id,request_id,operation,project_id,request_hash,result_json,at',
    'business_document_signatures': 'id,document_id,payload_sha256,actor_id,payload_json,at',
    'business_document_time_billing': 'document_id,entry_id,source_hash,source_revision,seconds',
    'business_document_versions': 'document_id,revision,payload_json,payload_sha256,at',
    'business_documents': 'id,project_id,customer_id,kind,status,revision,payload_json,payload_sha256,number,created_by,updated_by,created_at,updated_at,finalized_at',
    'business_dunning_approvals': 'id,proposal_id,document_id,level,payload_json,payload_sha256,pdf,pdf_sha256,approved_by,approved_at',
    'business_dunning_editions': 'id,approval_id,edition,supersedes_id,proposal_id,operation_id,payload_json,payload_sha256,pdf,pdf_sha256,approved_by,approved_at',
    'business_dunning_proposals': 'id,document_id,project_id,level,payload_json,payload_sha256,created_by,created_at',
    'business_dunning_rule_versions': 'revision,payload_json,payload_sha256,at',
    'business_dunning_settings': 'id,revision,payload_json,updated_by,updated_at',
    'business_employee_terms': 'employee_id,effective_from,revision,weekly_minutes,hourly_cost_minor',
    'business_employees': 'id,user_id,name,active,weekly_minutes,hourly_cost_minor,employment_from,employment_to,revision,updated_at',
    'business_euer_entries': 'id,sequence,operation,target,previous_hash,entry_json,entry_sha256,created_by,created_at',
    'business_euer_requests': 'user_id,request_id,request_json,request_hash,entry_id',
    'business_feature_flags': 'name,enabled,revision,updated_at',
    'business_feed': 'id,project_id,event_type,summary,visibility,refs_json,created_by,created_at',
    'business_finance_outbox': 'id,approval_id,operation_id,recipient,payload_sha256,created_at',
    'business_finance_requests': 'user_id,request_id,operation,request_hash,result_json,at',
    'business_financial_reconciliations': 'generation,restore_id,evidence_sha256,operator_name,reviewed_by,at',
    'business_foundation_requests': 'user_id,request_id,request_hash,result_json',
    'business_incoming_receipts': 'id,project_id,filename,media_type,original,sha256,payload_json,created_by,created_at',
    'business_instance_identity': 'singleton,instance_id,public_host,storage_root,vault_fingerprint,created_at',
    'business_inventory_adjustments': 'id,sequence_number,count_id,event_id,location_id,article_id,after_movement_sequence,quantity_delta,value_delta_net',
    'business_inventory_count_events': 'id,count_id,revision,operation,previous_hash,state_json,state_sha256,created_by,created_at',
    'business_inventory_count_requests': 'user_id,request_id,request_hash,event_id',
    'business_inventory_requests': 'user_id,request_id,request_hash,result_json',
    'business_lead_limits': 'adapter_id,window_started,window_count',
    'business_lead_reply_outbox': 'id,adapter_id,inquiry_id,template_id,operation_id,job_json,content_sha256,created_by,created_at',
    'business_lead_reply_receipts': 'id,outbox_id,operation_id,status,ordinal,receipt_id,error_code,at',
    'business_lead_reply_templates': 'id,adapter_id,revision,subject,text,enabled,approved_by,approved_at',
    'business_leads': 'id,adapter_id,external_id,inquiry_id,content_sha256,received_at',
    'business_maintenance_contracts': 'id,project_id,asset_id,payload_json,anchor_date,interval_unit,interval_count,next_index,active,revision,created_by,created_at,updated_by,updated_at',
    'business_maintenance_requests': 'user_id,request_id,request_hash,result_json',
    'business_maintenance_versions': 'kind,object_id,revision,project_id,payload_json',
    'business_maintenance_visits': 'id,project_id,contract_id,asset_id,due_date,occurrence_index,payload_json,status,report_id,report_pdf_sha256,revision,created_by,created_at,updated_by,updated_at',
    'business_media': 'id,project_id,filename,media_type,size,sha256,status,original,metadata_json,revision,created_by,created_at,updated_by,updated_at',
    'business_media_chunks': 'media_id,chunk_index,data,sha256',
    'business_operation_entries': 'id,project_id,kind,payload_json,content_hash,revision,pdf,pdf_sha256,created_by,created_at,updated_by,updated_at',
    'business_operation_versions': 'kind,object_id,revision,project_id,payload_json',
    'business_operations_requests': 'user_id,request_id,request_hash,result_json',
    'business_organization_events': 'revision,needs_json,modules_json,updated_by,updated_at',
    'business_organization_requests': 'user_id,request_id,request_hash,revision',
    'business_organization_settings': 'singleton,revision,needs_json,modules_json,updated_by,updated_at',
    'business_outbox_receipts': 'id,outbox_id,operation_id,outcome,ordinal,provider_receipt,created_by,created_at',
    'business_payment_allocations': 'id,payment_id,document_id,amount,created_at',
    'business_payments': 'id,source_id,kind,amount,currency,booking_date,reference,reverses,created_by,created_at',
    'business_payroll_events': 'id,kind,employee_id,revision,payload_json,content_hash,previous_hash,identity_key,created_by,created_at,pdf,pdf_sha256',
    'business_payroll_requests': 'user_id,request_id,request_hash,result_json',
    'business_permission_grants': 'id,user_id,permission,scope,effect,revision,updated_by,updated_at',
    'business_personnel_events': 'id,kind,employee_id,revision,payload_json,content_hash,previous_hash,created_by,created_at,pdf,pdf_sha256,identity_key',
    'business_personnel_files': 'id,employee_id,purpose,owner_visible,filename,media_type,size,sha256,content_hash,original,supersedes,created_by,created_at',
    'business_personnel_requests': 'user_id,request_id,request_hash,result_json',
    'business_planning_requests': 'user_id,request_id,operation,request_hash,result_json',
    'business_portal_adoptions': 'id,offer_id,decision_id,document_id,project_id,created_by,created_at',
    'business_portal_decision_requests': 'grant_id,principal_id,request_id,request_hash,decision_id',
    'business_portal_decisions': 'id,offer_id,grant_id,principal_id,source_revision,content_hash,pdf_hash,decision,declared_name,statement_version,statement_text,created_at',
    'business_portal_grants': 'id,principal_id,offer_id,number,project_id,customer_id,source_revision,content_hash,pdf_hash,public_json,secret_hash,expires_at,created_by,created_at',
    'business_portal_principals': 'id,customer_id,name,email,active,revision,created_by,created_at',
    'business_portal_rate_counters': 'key_hash,window_start,window_seconds,attempts,expires_at',
    'business_portal_revocations': 'grant_id,reason,kind,revoked_by,created_at',
    'business_portal_sessions': 'token_hash,grant_id,principal_id,created_at,expires_at',
    'business_portal_staff_requests': 'user_id,request_id,request_hash,operation,target_id',
    'business_privacy_anchors': 'installation_id,generation,digest',
    'business_privacy_requests': 'id,customer_id,operation,status,blockers_json,checkpoint_digest,created_by,created_at',
    'business_project_budgets': 'project_id,revision,material_net,labor_net,machine_net,other_net,updated_by,updated_at',
    'business_project_cost_requests': 'user_id,request_id,request_json,request_hash,entry_id',
    'business_project_cost_versions': 'id,project_id,receipt_id,revision,source_revision,original_sha256,previous_hash,entry_json,entry_sha256,created_by,created_at',
    'business_project_profiles': 'project_id,project_number,status_id,manager_id,site_address,description,revision,updated_by,updated_at',
    'business_project_statuses': 'id,name,color,position,terminal,active,revision,updated_by,updated_at',
    'business_purchase_confirmations': 'order_id,source_revision,source_json,source_sha256,order_reference,ordered_on,confirmed_by,confirmed_at',
    'business_purchase_orders': 'id,project_id,supplier_name,payload_json,status,revision,created_by,created_at,updated_by,updated_at',
    'business_purchase_receipt_lines': 'receipt_id,line_index,article_id,unit,quantity,unit_cost_net,cost_net,movement_id',
    'business_purchase_receipts': 'id,order_id,source_revision,receipt_revision,receipt_reference,reference_key,received_on,location_id,created_by,created_at',
    'business_purchasing_requests': 'user_id,request_id,request_hash,result_json',
    'business_receipt_reviews': 'receipt_id,revision,payload_json,payload_sha256,reviewed_by,reviewed_at',
    'business_resources': 'id,name,kind,active,code,revision,updated_at',
    'business_restore_state': 'singleton,pending,financial_reconciliation_required,restore_id',
    'business_sales_activities': 'id,opportunity_id,supersedes_id,payload_json,sha256,created_by,created_at',
    'business_sales_adoptions': 'opportunity_id,kind,project_id,document_id,payload_json,sha256,created_by,created_at',
    'business_sales_opportunities': 'id,customer_id,inquiry_id,created_by,created_at',
    'business_sales_requests': 'user_id,request_id,operation,request_json,request_hash,result_json',
    'business_sales_versions': 'opportunity_id,revision,payload_json,sha256,created_by,created_at',
    'business_schema_events': 'generation,compatibility_mode,at',
    'business_schema_migrations': 'module,version,checksum,applied_at',
    'business_schema_state': 'singleton,storage_version,compatibility_mode,generation,checksum',
    'business_signed_documents': 'signature_id,document_id,pdf,pdf_sha256,original_pdf_sha256,at',
    'business_stock_locations': 'id,name,active,revision,updated_by,updated_at',
    'business_stock_movements': 'id,sequence_number,kind,article_id,article_snapshot_json,from_location_id,to_location_id,project_id,quantity,unit_cost_net,cost_net,reversal_of,reservation_id,note,created_by,created_at',
    'business_stock_reorder_rules': 'location_id,article_id,minimum,target,updated_by,updated_at',
    'business_stock_reservations': 'id,project_id,article_id,location_id,article_snapshot_json,quantity,picked_quantity,status,revision,created_by,created_at,updated_by,updated_at',
    'business_templates': 'id,revision,payload_json,created_by,updated_by,created_at,updated_at',
    'business_text_blocks': 'id,revision,payload_json,updated_by,updated_at',
    'business_time_active': 'employee_id,entry_id',
    'business_time_adjustments': 'id,employee_id,effective_date,seconds,reason,created_by,created_at',
    'business_time_categories': 'id,name,supplement_percent,active,revision,updated_at',
    'business_time_corrections': 'id,entry_id,work_date,delta_seconds,reason,created_by,created_at',
    'business_time_days': 'employee_id,work_date,revision,status,worked_seconds,break_seconds,auto_pause_seconds,net_seconds,target_seconds,absence_seconds,rule_id,approved_by,approved_at',
    'business_time_entries': 'id,employee_id,project_id,category_id,status,started_at,ended_at,last_at,timezone,device_id,revision,last_sequence,hourly_cost_minor,supplement_percent,updated_at',
    'business_time_events': 'id,user_id,request_id,entry_id,action,occurred_at,received_at,device_id,sequence,expected_revision,request_hash,location_hash,location_redacted_at',
    'business_time_locations': 'event_id,employee_id,work_date,latitude,longitude,accuracy',
    'business_time_privacy': 'employee_id,work_date,checkpoint_generation,redacted_at',
    'business_time_requests': 'user_id,request_id,operation,request_hash,result_json',
    'business_time_rules': 'id,effective_from,revision,timezone,daily_target_minutes,auto_pause_after_minutes,auto_pause_minutes,second_after_minutes,second_pause_minutes,location_enabled,reminder_time,created_by,updated_at',
    'business_time_segments': 'entry_id,work_date,worked_seconds,break_seconds',
    'customers': 'id,name,contact,email,phone,address,notes,active,dedupe_key,created_at,updated_at',
    'external_bridge_jobs': 'id,provider,owner_id,kind,generation,requested_generation,resource,project_id,revision,selection_json,request_hash,status,payload_json,payload_sha256,source_id,error_code,created_at,expires_at,completed_at',
    'external_bridge_limits': 'provider,token_hash,window_start,request_count',
    'external_connections': 'provider,id,owner_id,config_cipher,credential_cipher,identity_json,generation,state,created_at,updated_at',
    'external_oauth_states': 'state_hash,provider,owner_id,session_hash,config_hash,generation,payload_cipher,expires_at,created_at',
    'external_project_links': 'project_id,provider,remote,selection_json,active,revision,generation,updated_by,updated_at,error_code',
    'external_requests': 'user_id,request_id,provider,operation,project_id,request_hash,result_json,created_at',
    'external_snapshots': 'project_id,provider,generation,revision,payload_json,payload_sha256,synced_at',
    'inbound_import_tokens': 'id,owner_id,name,source_account,token_hash,created_at,expires_at,revoked_at,last_used_at,window_started_at,window_count',
    'inquiries': 'id,source,source_account,source_id,source_fingerprint,subject,message,sender_name,sender_email,sender_phone,received_at,status,review_method,acceptance_channel,customer_id,project_id,next_action,due_date,sevdesk_url,provenance,revision,created_by,created_at,updated_at',
    'inquiry_attachment_chunks': 'attachment_id,chunk_index,data,sha256,size',
    'inquiry_attachment_limits': 'token_id,window_started_at,window_count',
    'inquiry_attachment_sets': 'inquiry_id,manifest_hash,expected_count,total_bytes,created_at',
    'inquiry_attachments': 'id,inquiry_id,source_attachment_id,filename,media_type,size,sha256,status,created_at,updated_at,deleted_at',
    'inquiry_requests': 'user_id,request_id,request_hash,result',
    'login_limits': 'key,failures,reset_at',
    'mfa': 'user_id,secret,last_step,recovery',
    'plan_deletions': 'deletion_id,kind,object_id,project_id,created_by,create_request_id,deleted_by,deleted_at,revision',
    'plan_import_chunks': 'import_id,chunk_index,data,sha256,size',
    'plan_imports': 'id,project_id,user_id,request_id,manifest_hash,filename,media_type,size,sha256,page,title,status,created_at,updated_at,attempts,lease_token,lease_until,error_code,preview,preview_sha256,result,result_sha256',
    'plan_requests': 'user_id,request_id,project_id,request_hash,result',
    'plan_sessions': 'token,user_id,expiry,credential',
    'plan_versions': 'id,revision,project_id,payload',
    'project_profiles': 'project_id,payload,revision,updated_by,updated_at',
    'projects': 'id,name,customer,customer_id',
    'reports': 'id,project_id,payload,pdf,pdf_hash,onedrive_id',
    'secrets': 'name,value',
    'sessions': 'token,user_id,expiry',
    'smartplan_schema': 'version',
    'users': 'id,email,salt,password,role,active',
    'workspace_items': 'id,project_id,kind,payload,revision,created_by,created_at,updated_by,updated_at',
    'workspace_requests': 'user_id,request_id,project_id,request_hash,result',
    'workspace_versions': 'kind,object_id,revision,project_id,payload',
}

EXCLUDED = {
    'business_privacy_case_contents': 'restricted_subject_request_working_material_case_authorization_only',
    'business_privacy_case_export_blobs': 'restricted_subject_request_working_material_case_authorization_only',
    'secrets': 'provider_credentials_and_encrypted_settings',
    'sessions': 'active_authentication', 'plan_sessions': 'active_device_authentication',
    'mfa': 'authentication_secrets', 'auth_challenges': 'authentication_secrets',
    'login_limits': 'ephemeral_security_counters', 'external_oauth_states': 'authentication_secrets',
    'inbound_import_tokens': 'active_connector_credentials', 'business_device_grants': 'active_device_authentication',
    'business_customer_sessions': 'active_customer_authentication', 'business_portal_sessions': 'active_customer_authentication',
    'business_portal_rate_counters': 'ephemeral_security_counters', 'external_bridge_limits': 'ephemeral_security_counters',
    'business_lead_limits': 'ephemeral_security_counters', 'business_contact_form_limits': 'ephemeral_security_counters',
    'inquiry_attachment_limits': 'ephemeral_security_counters',
}
EXCLUDED.update({table:'technical_idempotency_receipts_not_a_restorable_database'
                 for table in COLUMNS if table.endswith('_requests') and table not in
                 ('business_privacy_requests','business_assistant_speech_requests')})
OMITTED_COLUMNS = {
    'users': {'salt','password'}, 'external_connections': {'config_cipher','credential_cipher'},
    'business_adapters': {'secret_ref'}, 'business_instance_identity': {'storage_root','vault_fingerprint'},
    'business_customer_grants': {'secret_hash'}, 'business_portal_grants': {'secret_hash'},
    'plan_imports': {'lease_token'}, 'business_company_exports': {'archive'},
}
OPTIONAL_COLUMNS = {'reports': {'rowid'}}


def policy(table):
    if table not in COLUMNS:
        raise ValueError('Unclassified export table: '+table)
    financial=any(value in table for value in ('accounting','euer','document','finance','payment','receipt','payroll','business_bank_')) or table=='business_travel_cash_events'
    personnel=any(value in table for value in ('personnel','payroll','employee','absence','time_')) or (table.startswith('business_travel_') and table!='business_travel_cash_events')
    authentication=table in EXCLUDED or table in ('users','external_connections','business_permission_grants')
    if personnel:
        category,purpose='personnel','Employment, working time, payroll and evidence of expenses'
        retention='Employment/social-security/tax duties and applicable claims; case-specific review required'
    elif financial:
        category,purpose='financial','Commercial originals, cash transactions and reconstructable accounting history'
        retention='Applicable commercial/tax recordkeeping and claims; record-specific review required'
    elif authentication:
        category,purpose='security','Accountability, access control and integration operation'
        retention='Security purpose and documented minimum duration; revoke access separately from records'
    elif any(value in table for value in ('schema','restore','privacy_anchors','instance_identity')):
        category,purpose='system','Data structure, installation binding and historical reconciliation'
        retention='Keep with the associated retained evidence; operator review required'
    else:
        category,purpose='business','Customer, project, operational and supplier records including historical decisions'
        retention='Contract purpose, applicable evidence duties and claims; case-specific review required'
    result=dict(table=table,category=category,purpose=purpose,
        personal_data=category!='system',sensitive=personnel or financial or table in ('business_time_locations','business_customer_uploads','inquiry_attachments'),
        retention_basis=retention,retention_days=None,access='active_owner_only',
        included=table not in EXCLUDED,exclusion_reason=EXCLUDED.get(table),
        omitted_columns=sorted(OMITTED_COLUMNS.get(table,set())),columns=COLUMNS[table].split(','))
    if table in ('business_payroll_account_events','business_payroll_events'):
        result['retention_rule']={
            'legal_basis':'EStG § 41 Absatz 1 Satz 9; ergänzende Unterlagen nach Satz 10 gesondert zuordnen',
            'source':'https://www.gesetze-im-internet.de/estg/__41.html',
            'scope':'Lohnkonto und darin referenzierte bezahlte Lohnläufe einschließlich ihrer Profil-/Berechnungsquellen',
            'trigger':'last_recorded_wage_payment_date',
            'end':'end_of_sixth_calendar_year_following_payment_year',
            'example':{'last_payment_date':'2026-11-30','retain_through':'2032-12-31'},
            'other_retention_or_legal_holds_must_be_reviewed':True,
            'not_a_blanket_deadline_for_unpaid_runs_or_personnel_files':True,
        }
    if table=='business_payroll_account_requests':
        result['purpose']='Technical retry receipts containing personal payroll account result snapshots'
        result['retention_basis']='Linked payroll evidence and retry purpose; source-dependent review, no independent blanket period'
    if table.startswith('business_custom_field_'):
        result['sensitive']=True
        result['purpose']='Versioned customer/project/asset field definitions and values; may contain confidential personal free text'
        result['retention_basis']='Purpose and retention of the associated customer/project/asset record; case-specific review required'
    if table.startswith('business_migration_'):
        result['sensitive']=True
        result['purpose']='Original CRM/financial migration files, mappings, adoption bindings and reconciliation evidence'
        result['retention_basis']='Applicable obligations of the original records and documented migration evidence; source-specific review required'
    if table.startswith('business_privacy_case_'):
        result['sensitive']=True
        result['purpose']='Restricted subject-rights case handling and minimal checkpoint-protected purge/restore evidence'
        result['retention_basis']='Private contents use explicit case retain_until/hold; private exports use expires_on; minimal hashes document purge/restore, no universal legal duration'
        result['source_access']='Assigned case handlers; minimal evidence after purge restricted to owner'
    if table.startswith('business_service_'):
        result['sensitive']=True
        result['purpose']='Customer service and complaint cases, contact notes, native planning/project and signed-report evidence links'
    if table.startswith('business_bank_'):
        result['sensitive']=True
        result['purpose']='Original bank statements, account identity, counterparties/references and explicit reconciliation history of existing cash flows'
        result['retention_basis']='Applicable financial evidence and original statement duties; source-specific review, no universal legal duration'
    if table.startswith('business_accounting_asset_opening_'):
        result['sensitive']=True
        result['purpose']='Evidenced historical linear asset balances and immutable original depreciation carryover; no new acquisition, cash movement or input tax claim'
        result['retention_basis']='Applicable original financial and asset register duties; source-specific review, no universal legal duration'
        result['source_access']='Current global accounting read and finance read access'
    if table.startswith('business_accounting_opening_'):
        result['sensitive']=True
        result['purpose']='Evidenced opening account balances and immutable correction history; original financial documents, no new cash or tax transaction'
        result['retention_basis']='Applicable original financial evidence and transfer duties; source-specific review, no universal legal duration'
        result['source_access']='Current global accounting read, finance read and bank read access'
    if table.startswith('business_resource_') and table in COLUMNS:
        result['sensitive']=True
        result['purpose']='Resource custody, employee/project handoffs and returns, inspection evidence and immutable corrections with personal original documents'
        result['retention_basis']='Source-specific equipment, inspection, employment and liability evidence; documented applicable duties and holds, no universal duration'
        result['source_access']='Planning read/write roles; linked employee/project and original evidence must be reviewed for the specific subject request'
    if table in ('business_purchase_amendments','business_purchase_receipt_terms',
                 'business_supplier_returns','business_supplier_return_lines',
                 'business_purchase_change_evidence','business_purchase_change_requests'):
        result['sensitive']=True
        result['purpose']='Supplier originals, evidenced quantity amendments and actual stock returns; may contain financial and third-party personal information'
        result['retention_basis']='Source-specific commercial, stock and contractual evidence with documented holds; no blanket deletion period'
        result['source_access']='Actual order project inventory access; prices and original documents additionally require current financial read access'
    return result


def catalog():
    return [policy(table) for table in sorted(COLUMNS)]
