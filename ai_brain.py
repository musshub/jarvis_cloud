import json
import os
from typing import Dict, Any, Optional, List

from openai import OpenAI

from memory_rules import memory_to_prompt


class JarvisBrain:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("JARVIS_MODEL", "gpt-4o-mini")

    def answer_or_plan(
        self,
        *,
        user_id: str,
        command: str,
        memory: Dict[str, Any],
        location: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        system = self._system_prompt(memory)

        location_text = ""
        if location:
            location_text = (
                f"\nUSER LOCATION PROVIDED: "
                f"lat={location.get('lat')}, lon={location.get('lon')}\n"
            )

        user_prompt = (
            f"User command:\n{command}\n"
            f"{location_text}\n"
            "Return ONLY valid JSON. No markdown."
        )

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        )

        text = self._extract_text(response)

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return self._normalize(data, command)
        except Exception:
            pass

        return {
            "mode": "answer",
            "answer": text.strip(),
            "action": "chat",
            "project_hint": "unknown",
            "requires_confirmation": False,
            "requires_backup": False,
            "task_payload": {},
        }

    def generate_file_updates(
        self,
        *,
        user_id: str,
        command: str,
        memory: Dict[str, Any],
        project_hint: str,
        project_path: str,
        files: List[Dict[str, Any]],
        analyze_output: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._code_update_call(
            command=command,
            memory=memory,
            project_hint=project_hint,
            project_path=project_path,
            files=files,
            analyze_output=analyze_output,
            repair=False,
            previous_updates=[],
            attempt=0,
        )

    def generate_repair_updates(
        self,
        *,
        user_id: str,
        command: str,
        memory: Dict[str, Any],
        project_hint: str,
        project_path: str,
        files: List[Dict[str, Any]],
        analyze_output: Dict[str, Any],
        previous_updates: List[Dict[str, Any]],
        attempt: int,
    ) -> Dict[str, Any]:
        return self._code_update_call(
            command=command,
            memory=memory,
            project_hint=project_hint,
            project_path=project_path,
            files=files,
            analyze_output=analyze_output,
            repair=True,
            previous_updates=previous_updates,
            attempt=attempt,
        )

    def _code_update_call(
        self,
        *,
        command: str,
        memory: Dict[str, Any],
        project_hint: str,
        project_path: str,
        files: List[Dict[str, Any]],
        analyze_output: Dict[str, Any],
        repair: bool = False,
        previous_updates: Optional[List[Dict[str, Any]]] = None,
        attempt: int = 0,
    ) -> Dict[str, Any]:
        system = (
            self._repair_system_prompt(memory)
            if repair
            else self._code_system_prompt(memory)
        )

        compact_files = [
            {
                "path": f.get("path"),
                "score": f.get("score", 0),
                "content": f.get("content", ""),
            }
            for f in files
        ]

        payload = {
            "user_command": command,
            "project_hint": project_hint,
            "project_path": project_path,
            "files": compact_files,
            "flutter_analyze": {
                "ok": analyze_output.get("ok"),
                "stdout": (analyze_output.get("stdout") or "")[-12000:],
                "stderr": (analyze_output.get("stderr") or "")[-12000:],
                "returncode": analyze_output.get("returncode"),
            },
            "previous_updates": previous_updates or [],
            "repair_attempt": attempt,
        }

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        "Input JSON:\n"
                        + json.dumps(payload, ensure_ascii=False)
                        + "\nReturn ONLY valid JSON. No markdown."
                    ),
                },
            ],
        )

        text = self._extract_text(response)

        try:
            data = json.loads(text)
            updates = []

            if isinstance(data, dict):
                for item in data.get("updates", []):
                    if not isinstance(item, dict):
                        continue

                    path = str(item.get("path") or "").strip()
                    new_content = item.get("new_content")

                    if path and isinstance(new_content, str):
                        updates.append(
                            {
                                "path": path,
                                "new_content": new_content,
                                "reason": str(item.get("reason") or ""),
                            }
                        )

                return {
                    "ok": True,
                    "summary": str(
                        data.get("summary") or "Code updates generated."
                    ),
                    "updates": updates,
                    "warnings": data.get("warnings")
                    if isinstance(data.get("warnings"), list)
                    else [],
                }
        except Exception as e:
            return {
                "ok": False,
                "summary": "AI response was not valid JSON.",
                "updates": [],
                "warnings": [str(e), text[:2000]],
            }

        return {
            "ok": False,
            "summary": "AI did not return valid JSON.",
            "updates": [],
            "warnings": [text[:2000]],
        }

    def analyze_phone_screenshot(
        self,
        *,
        command: str,
        image_base64: str,
        image_mime: str = "image/png",
    ) -> Dict[str, Any]:
        system = """
You are Jarvis Phone Vision Agent.
Inspect Android screenshots and identify UI elements.
Return ONLY valid JSON with:
ok, screen_summary, target_found,
target {label,type,x,y,confidence},
visible_elements, recommended_action, reason.
Coordinates must match screenshot pixels.
"""

        response = self.client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"User command:\n{command}\n"
                                "Analyze this phone screenshot and return JSON only."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{image_mime};base64,{image_base64}"
                            ),
                        },
                    ],
                },
            ],
        )

        text = self._extract_text(response)

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data.setdefault("ok", True)
                return data
        except Exception as e:
            return {
                "ok": False,
                "error": f"Vision JSON parse failed: {e}",
                "raw": text[:3000],
            }

        return {
            "ok": False,
            "error": "Vision response was not usable.",
            "raw": text[:3000],
        }

    def _system_prompt(self, memory: Dict[str, Any]) -> str:
        return f"""
You are Shub Jarvis, a personal AI operator for Shubham.

You are talkative, practical, friendly, and understand Hindi-English mixed commands.

Important:
- For normal conversation, answer directly.
- For current/latest/news questions, answer from general knowledge only for now and clearly say live web search is not enabled yet.
- If user asks to remember something, mode must be memory_update.
- If user asks to inspect/fix/edit/build/backup Flutter project, mode must be pc_task.
- If editing files, action must be edit_project_files and requires_backup must be true.
- WhatsApp is draft only, never send automatically.
- Phone control is through PC Worker ADB, so phone tasks should usually be mode pc_task.
- For casual Hindi-English like "aur bhai kya", answer naturally as Jarvis.

{memory_to_prompt(memory)}

Return ONLY JSON:
{{
  "mode": "answer | pc_task | phone_task | memory_update | location_task",
  "answer": "natural answer",
  "action": "chat | web_answer | remember_rule | inspect_project | create_flutter_prototype | edit_project_files | flutter_analyze | flutter_build_apk | backup_project | phone_whatsapp_draft | phone_open_app | phone_screenshot | phone_test_app | phone_contact_lookup | phone_tap | phone_type_text | phone_run_flow | phone_nirmansutra_billing_flow | phone_vision_analyze | phone_vision_tap | nearest_petrol_pump | describe_location",
  "project_hint": "nirmansutra | gallery_pro | shub_ai | unknown | new_project",
  "requires_confirmation": false,
  "requires_backup": false,
  "task_payload": {{
    "summary": "",
    "steps": [],
    "message": "",
    "contact_name": "",
    "phone_number": "",
    "app_idea": "",
    "search_query": "",
    "target_label": ""
  }}
}}
"""

    def _code_system_prompt(self, memory: Dict[str, Any]) -> str:
        return f"""
You are Jarvis Code Editor for Shubham's Flutter projects.
Improve/fix only provided files.
Return full updated file contents, not patches.
Avoid Firestore composite indexes.
Do not remove business logic silently.

{memory_to_prompt(memory)}

Return ONLY JSON with:
summary, updates[path,reason,new_content], warnings.
"""

    def _repair_system_prompt(self, memory: Dict[str, Any]) -> str:
        return f"""
You are Jarvis Flutter Repair Agent.
Fix ONLY analyzer/compile errors after previous edits.
Return full files only.
Use analyzer output as source of truth.

{memory_to_prompt(memory)}

Return ONLY JSON with:
summary, updates[path,reason,new_content], warnings.
"""

    def _extract_text(self, response: Any) -> str:
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text

        chunks = []
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(text)

        return "\n".join(chunks)

    def _normalize(self, data: Dict[str, Any], command: str) -> Dict[str, Any]:
        allowed = {
            "answer",
            "pc_task",
            "phone_task",
            "memory_update",
            "location_task",
        }

        mode = data.get("mode")
        if mode not in allowed:
            mode = "answer"

        return {
            "mode": mode,
            "answer": str(data.get("answer") or ""),
            "action": data.get("action") or "chat",
            "project_hint": data.get("project_hint") or "unknown",
            "requires_confirmation": bool(data.get("requires_confirmation", False)),
            "requires_backup": bool(data.get("requires_backup", False)),
            "task_payload": data.get("task_payload")
            if isinstance(data.get("task_payload"), dict)
            else {},
            "original_command": command,
        }