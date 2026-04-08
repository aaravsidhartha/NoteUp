content = open('backend/api/orchestrator.py').read()

old_sig = '        conversation_history: Optional[str] = "",\n    ) -> str:'
new_sig = '        conversation_history: Optional[str] = "",\n        pdf_id: Optional[str] = "",\n    ) -> str:'

old_json = '"conversation_history": conversation_history or "",'
new_json = '"conversation_history": conversation_history or "",\n                    "pdf_id": pdf_id or "",'

content = content.replace(old_sig, new_sig)
content = content.replace(old_json, new_json)

open('backend/api/orchestrator.py', 'w').write(content)
print('done')