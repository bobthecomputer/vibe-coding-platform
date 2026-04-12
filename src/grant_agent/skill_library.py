from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict
from pathlib import Path

from .models import (
    LearnedSkill,
    SkillPack,
    SkillPromotionCandidate,
    SkillSource,
    SkillUsageRecord,
    utc_now_iso,
)
from .skills import Skill, SkillRegistry


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class SkillLibrary:
    def __init__(self, root: Path, registry: SkillRegistry) -> None:
        self.root = root.resolve()
        self.registry = registry
        self.control_dir = self.root / ".agent_control"
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.learned_path = self.control_dir / "learned_skills.json"
        self.user_installed_path = self.control_dir / "user_installed_skills.json"
        self.usage_path = self.control_dir / "skill_usage.json"
        self.learned_skills = self._load_learned_skills()
        self.user_installed_skills = self._load_skill_rows(self.user_installed_path)
        self.usage_records = self._load_usage_records()

    def _load_skill_rows(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_usage_records(self) -> list[SkillUsageRecord]:
        payload = self._load_skill_rows(self.usage_path)
        return [SkillUsageRecord(**item) for item in payload]

    def _load_learned_skills(self) -> list[LearnedSkill]:
        payload = self._load_skill_rows(self.learned_path)
        learned: list[LearnedSkill] = []
        for item in payload:
            source = SkillSource(**item.get("source", {"kind": "learned", "label": "Learned"}))
            learned.append(
                LearnedSkill(
                    skill_id=item["skill_id"],
                    label=item["label"],
                    description=item.get("description", ""),
                    prompt_hint=item.get("prompt_hint", ""),
                    source=source,
                    confidence=float(item.get("confidence", 0.0)),
                    status=item.get("status", "learned"),
                    disabled=bool(item.get("disabled", False)),
                    usage_count=int(item.get("usage_count", 0)),
                    tags=item.get("tags", []),
                    permissions=item.get("permissions", []),
                    audit=item.get("audit", []),
                    created_at=item.get("created_at", utc_now_iso()),
                    updated_at=item.get("updated_at", utc_now_iso()),
                    last_used_at=item.get("last_used_at"),
                )
            )
        return learned

    def _save_learned_skills(self) -> None:
        self.learned_path.write_text(
            json.dumps([asdict(item) for item in self.learned_skills], indent=2),
            encoding="utf-8",
        )

    def _save_usage_records(self) -> None:
        self.usage_path.write_text(
            json.dumps([asdict(item) for item in self.usage_records], indent=2),
            encoding="utf-8",
        )

    def curated_packs(self) -> list[SkillPack]:
        packs: list[SkillPack] = []
        for skill in self.registry.skills:
            packs.append(
                SkillPack(
                    pack_id=f"curated:{skill.name}",
                    label=skill.name.replace("_", " ").title(),
                    description=skill.description,
                    source=SkillSource(kind="curated", label="Curated"),
                    recommended=True,
                    installed=True,
                    skills=[skill.name],
                    permissions=skill.permissions,
                    audience="all",
                    action_kinds=skill.action_kinds,
                    profile_suitability=skill.profile_suitability,
                    guidance_only=skill.guidance_only,
                    execution_capable=skill.execution_capable,
                )
            )
        return packs

    def learned_skill_rows(self) -> list[dict]:
        return [asdict(item) for item in self.learned_skills]

    def _usage_summary(self, skill_id: str) -> dict[str, str | int | None]:
        records = [item for item in self.usage_records if item.skill_id == skill_id]
        helped = [item for item in records if item.helped]
        last_used_at = max((item.created_at for item in records), default=None)
        last_helped_at = max((item.created_at for item in helped), default=None)
        return {
            "usageCount": len(records),
            "helpedCount": len(helped),
            "lastUsedAt": last_used_at,
            "lastHelpedAt": last_helped_at,
        }

    def _enrich_catalog_row(
        self,
        row: dict,
        *,
        default_origin_type: str,
        default_editable_status: str,
        default_test_status: str,
        default_promotion_state: str,
    ) -> dict:
        item = dict(row)
        source = item.get("source", {}) if isinstance(item.get("source"), dict) else {}
        skill_id = (
            item.get("skillId")
            or item.get("skill_id")
            or item.get("packId")
            or item.get("pack_id")
            or item.get("label")
            or item.get("name")
            or ""
        )
        usage = self._usage_summary(str(skill_id))

        if item.get("disabled"):
            editable_status = "disabled"
        elif item.get("archived"):
            editable_status = "archived"
        else:
            editable_status = (
                item.get("editableStatus")
                or item.get("editable_status")
                or item.get("status")
                or default_editable_status
            )

        origin_type = (
            item.get("originType")
            or item.get("origin_type")
            or source.get("kind")
            or default_origin_type
        )
        test_status = (
            item.get("testStatus")
            or item.get("test_status")
            or default_test_status
        )
        promotion_state = (
            item.get("promotionState")
            or item.get("promotion_state")
            or default_promotion_state
        )

        if "skill_id" in item and "skillId" not in item:
            item["skillId"] = item["skill_id"]
        if "pack_id" in item and "packId" not in item:
            item["packId"] = item["pack_id"]
        if "prompt_hint" in item and "promptHint" not in item:
            item["promptHint"] = item["prompt_hint"]

        item.update(
            {
                "editableStatus": editable_status,
                "testStatus": test_status,
                "promotionState": promotion_state,
                "lastUsedAt": item.get("lastUsedAt") or item.get("last_used_at") or usage["lastUsedAt"],
                "lastHelpedAt": item.get("lastHelpedAt") or item.get("last_helped_at") or usage["lastHelpedAt"],
                "originType": origin_type,
                "usageCount": item.get("usageCount", usage["usageCount"]),
                "helpedCount": item.get("helpedCount", usage["helpedCount"]),
            }
        )
        return item

    def _normalized_user_installed_skills(self) -> list[dict]:
        rows: list[dict] = []
        for item in self.user_installed_skills:
            source = item.get("source", {}) if isinstance(item.get("source"), dict) else {}
            origin_type = (
                item.get("originType")
                or item.get("origin_type")
                or source.get("kind")
                or "user_authored"
            )
            promotion_state = "imported" if origin_type == "imported" else "reviewed"
            rows.append(
                self._enrich_catalog_row(
                    item,
                    default_origin_type=origin_type,
                    default_editable_status="active",
                    default_test_status="untested",
                    default_promotion_state=promotion_state,
                )
            )
        return rows

    @staticmethod
    def _management_summary(sections: list[list[dict]]) -> dict[str, int]:
        items = [item for section in sections for item in section]
        return {
            "totalSkills": len(items),
            "needsTestCount": sum(
                1 for item in items if item.get("testStatus") in {"untested", "pending", "sample_ready"}
            ),
            "reviewedReusableCount": sum(
                1 for item in items if item.get("promotionState") == "reviewed"
            ),
            "learnedCount": sum(1 for item in items if item.get("originType") == "learned"),
            "disabledCount": sum(
                1 for item in items if item.get("editableStatus") in {"disabled", "archived"}
            ),
        }

    def build_catalog(
        self,
        recommended_packs: list[SkillPack] | None = None,
    ) -> dict[str, list[dict]]:
        curated = [
            self._enrich_catalog_row(
                asdict(item),
                default_origin_type="curated",
                default_editable_status="active",
                default_test_status="reviewed",
                default_promotion_state="reviewed",
            )
            for item in self.curated_packs()
        ]
        learned = [
            self._enrich_catalog_row(
                asdict(item),
                default_origin_type="learned",
                default_editable_status="disabled" if item.disabled else "active",
                default_test_status="untested",
                default_promotion_state="learning",
            )
            for item in self.learned_skills
        ]
        user_installed = self._normalized_user_installed_skills()
        recommended = [
            self._enrich_catalog_row(
                asdict(item),
                default_origin_type="curated",
                default_editable_status="available",
                default_test_status="recommended",
                default_promotion_state="recommended",
            )
            for item in (recommended_packs or [])
        ]
        sections = [recommended, curated, user_installed, learned]
        return {
            "curatedPacks": curated,
            "recommendedPacks": recommended,
            "userInstalledSkills": user_installed,
            "learnedSkills": learned,
            "managementSummary": self._management_summary(sections),
        }

    def retrieve(
        self,
        task_brief: str,
        top_k: int = 4,
    ) -> list[dict]:
        curated = self.registry.retrieve(task_brief=task_brief, top_k=top_k)
        learned_candidates = [
            item for item in self.learned_skills if not item.disabled
        ]
        query_tokens = _tokenize(task_brief)

        def learned_score(item: LearnedSkill) -> tuple[int, float, int]:
            text_tokens = _tokenize(
                " ".join([item.label, item.description, item.prompt_hint, " ".join(item.tags)])
            )
            return len(query_tokens & text_tokens), item.confidence, item.usage_count

        ranked_learned = sorted(
            learned_candidates, key=learned_score, reverse=True
        )[:top_k]
        merged: list[dict] = []
        for skill in curated:
            merged.append(
                {
                    "skillId": skill.name,
                    "label": skill.name.replace("_", " ").title(),
                    "description": skill.description,
                    "permissions": skill.permissions,
                    "sourceKind": "curated",
                    "actionKinds": skill.action_kinds,
                    "profileSuitability": skill.profile_suitability,
                    "guidanceOnly": skill.guidance_only,
                    "executionCapable": skill.execution_capable,
                }
            )
        for skill in ranked_learned:
            merged.append(
                {
                    "skillId": skill.skill_id,
                    "label": skill.label,
                    "description": skill.description,
                    "permissions": skill.permissions,
                    "sourceKind": "learned",
                    "confidence": skill.confidence,
                    "actionKinds": skill.tags,
                    "profileSuitability": ["builder", "advanced", "experimental"],
                    "guidanceOnly": False,
                    "executionCapable": True,
                }
            )
        return merged[:top_k]

    def record_usage(
        self,
        skill_id: str,
        label: str,
        step_id: str,
        mission_id: str,
        helped: bool,
        source_kind: str,
    ) -> SkillUsageRecord:
        record = SkillUsageRecord(
            skill_id=skill_id,
            label=label,
            step_id=step_id,
            mission_id=mission_id,
            helped=helped,
            source_kind=source_kind,
        )
        self.usage_records.append(record)
        self._save_usage_records()
        for learned in self.learned_skills:
            if learned.skill_id == skill_id:
                learned.usage_count += 1
                learned.last_used_at = record.created_at
                learned.updated_at = record.created_at
        self._save_learned_skills()
        return record

    def suggest_promotions(
        self,
        mission_id: str,
        objective: str,
        selected_skills: list[dict],
        verification_failures: list[str],
    ) -> list[SkillPromotionCandidate]:
        if verification_failures:
            return []

        candidates: list[SkillPromotionCandidate] = []
        lowered = objective.lower()
        if "test" in lowered or "verify" in lowered:
            candidates.append(
                SkillPromotionCandidate(
                    candidate_id=f"promo_{uuid.uuid4().hex[:10]}",
                    label="Verification Loop",
                    reason="Successful missions repeatedly benefit from a shared verification routine.",
                    confidence=0.74,
                    evidence=[item["label"] for item in selected_skills],
                )
            )
        if "repo" in lowered or "workspace" in lowered or "control" in lowered:
            candidates.append(
                SkillPromotionCandidate(
                    candidate_id=f"promo_{uuid.uuid4().hex[:10]}",
                    label="Repo Grounding Loop",
                    reason="The harness repeatedly grounded itself in workspace structure before acting.",
                    confidence=0.68,
                    evidence=[mission_id],
                )
            )
        return candidates

    def promote_candidates(
        self,
        candidates: list[SkillPromotionCandidate],
    ) -> list[LearnedSkill]:
        promoted: list[LearnedSkill] = []
        for candidate in candidates:
            existing = next(
                (item for item in self.learned_skills if item.label == candidate.label),
                None,
            )
            if existing:
                existing.confidence = max(existing.confidence, candidate.confidence)
                existing.usage_count += 1
                existing.audit.append(
                    f"{utc_now_iso()}: reinforced by promotion candidate {candidate.candidate_id}"
                )
                existing.updated_at = utc_now_iso()
                promoted.append(existing)
                continue

            learned = LearnedSkill(
                skill_id=f"learned_{uuid.uuid4().hex[:10]}",
                label=candidate.label,
                description=candidate.reason,
                prompt_hint="Apply this learned pattern when the mission matches previous successful evidence.",
                source=SkillSource(kind="learned", label="Learned"),
                confidence=candidate.confidence,
                usage_count=1,
                audit=[
                    f"{utc_now_iso()}: promoted from candidate {candidate.candidate_id}"
                ],
                tags=["learned", "reviewable"],
            )
            self.learned_skills.append(learned)
            promoted.append(learned)
        self._save_learned_skills()
        return promoted

    @staticmethod
    def recommended_packs_from_skills(
        recommendations: list[dict],
    ) -> list[SkillPack]:
        packs: list[SkillPack] = []
        for item in recommendations:
            packs.append(
                SkillPack(
                    pack_id=f"recommended:{item['recommendation_id']}",
                    label=item["label"],
                    description=item["reason"],
                    source=SkillSource(kind="recommended", label="Recommended"),
                    recommended=True,
                    installed=False,
                    skills=[item["recommendation_id"]],
                    permissions=["file_read"],
                    audience="guided",
                    action_kinds=["workspace_search", "file_read"],
                    profile_suitability=["beginner", "builder"],
                    guidance_only=False,
                    execution_capable=True,
                )
            )
        return packs
