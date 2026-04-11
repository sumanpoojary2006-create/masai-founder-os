"""Practical operational playbooks that execute real business actions."""

from __future__ import annotations

import re
from typing import Dict, List, Optional

try:
    from ai_company.core.communications import EmailService
    from ai_company.core.database import Database
except ImportError:
    from core.communications import EmailService
    from core.database import Database


class OperationalPlaybooks:
    """Execute deterministic business workflows after department reasoning."""

    TEAM_EMAIL_META = {
        "sales": {
            "team_name": "Masai Sales Team",
            "subject_prefix": "Admissions update",
            "default_summary": "We are reaching out with the next best admissions step for you.",
            "bullets": [
                "We reviewed your current admissions context and prepared the next recommended action.",
                "Reply to this email if you want a counselor callback or application support.",
                "Our team can help you move from inquiry to application with one guided step.",
            ],
        },
        "ops": {
            "team_name": "Masai Ops Team",
            "subject_prefix": "Operations update",
            "default_summary": "We are sharing the latest update about your cohort operations or learner journey.",
            "bullets": [
                "Your request has been picked up by the operations team.",
                "We have documented the next operational step in the system.",
                "Reply if you want a manual callback from the ops desk.",
            ],
        },
        "curriculum": {
            "team_name": "Masai Curriculum Team",
            "subject_prefix": "Learning update",
            "default_summary": "We are sharing the next academic recommendation from the curriculum team.",
            "bullets": [
                "We reviewed the academic context behind your request.",
                "The curriculum team has documented the next learning recommendation.",
                "Reply if you want a mentor or curriculum callback.",
            ],
        },
        "accounts": {
            "team_name": "Masai Accounts Team",
            "subject_prefix": "Accounts update",
            "default_summary": "We are sharing the latest finance or payment update from the accounts team.",
            "bullets": [
                "Your finance-related request has been reviewed by accounts.",
                "The relevant payment or refund note has been logged in the system.",
                "Reply if you want the team to share the next payment action or reference.",
            ],
        },
        "tech": {
            "team_name": "Masai Tech Team",
            "subject_prefix": "Platform update",
            "default_summary": "We are sharing a technical update about your platform-related request.",
            "bullets": [
                "The technical issue or request has been reviewed by the platform team.",
                "A concrete next step has been documented for the product or engineering flow.",
                "Reply if you want an updated ETA or issue reference number.",
            ],
        },
    }

    def __init__(self, db: Database, email_service: Optional[EmailService] = None) -> None:
        self.db = db
        self.email_service = email_service or EmailService()

    def execute(self, department: str, task_request: str, ai_response: str, task_id: str) -> Dict[str, object]:
        """Run a concrete workflow when the request matches a supported pattern."""
        if self.supports(department, task_request):
            lowered = task_request.lower()
        else:
            return {
                "summary": self.db.apply_department_action(department, task_request, ai_response),
                "events": [],
            }

        if department == "sales" and "webinar" in lowered and any(
            word in lowered for word in ("email", "mail", "follow-up", "follow up", "reach out", "send")
        ):
            return self._run_webinar_follow_up(task_request, ai_response, task_id)
        if department == "accounts" and "refund" in lowered:
            return self._run_refund_initiation(task_request, ai_response, task_id)
        if any(word in lowered for word in ("email", "mail", "notify", "message", "send")):
            return self._run_team_email(task_request, ai_response, task_id, department)

        return {"summary": self.db.apply_department_action(department, task_request, ai_response), "events": []}

    def supports(self, department: str, task_request: str) -> bool:
        """Return whether a deterministic practical playbook exists for this request."""
        lowered = task_request.lower()
        return (
            department == "sales"
            and "webinar" in lowered
            and any(word in lowered for word in ("email", "mail", "follow-up", "follow up", "reach out", "send"))
        ) or (department == "accounts" and "refund" in lowered) or any(
            word in lowered for word in ("email", "mail", "notify", "message", "send")
        )

    def _extract_city(self, task_request: str) -> str:
        lowered = task_request.lower()
        for city in ("bangalore", "mumbai", "delhi", "chennai"):
            if city in lowered:
                return city.title()
        return ""

    def _extract_amount(self, task_request: str) -> Optional[int]:
        candidates = []
        for match in re.finditer(r"(?:rs\.?|inr|₹)?\s*([0-9][0-9,]{2,})", task_request, re.IGNORECASE):
            value = match.group(1).replace(",", "")
            start_index = match.start(1)
            prefix = task_request[max(0, start_index - 1) : start_index].lower()
            if prefix == "s":
                continue
            candidates.append(int(value))
        if not candidates:
            return None
        return max(candidates)

    def _clean_ai_summary(self, ai_response: str, fallback: str) -> str:
        """Strip markdown-like noise and compress the AI response into one readable sentence."""
        cleaned = re.sub(r"[*#`_>-]+", " ", ai_response or "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned[:240] if cleaned else fallback

    def _render_email_html(self, title: str, greeting: str, intro: str, bullets: List[str], closing: str, team_name: str) -> str:
        bullet_items = "".join(f"<li>{item}</li>" for item in bullets if item)
        return f"""
        <html>
          <body style="margin:0;background:#f6f1e8;font-family:Arial,sans-serif;color:#1f2937;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 0;">
              <tr>
                <td align="center">
                  <table role="presentation" width="640" cellspacing="0" cellpadding="0" style="max-width:640px;background:#fffdf8;border:1px solid #eadfc8;border-radius:20px;overflow:hidden;">
                    <tr>
                      <td style="background:#17332d;color:#f8f2e7;padding:20px 28px;">
                        <div style="font-size:12px;letter-spacing:1.6px;text-transform:uppercase;opacity:0.78;">Masai Founder OS</div>
                        <div style="font-size:26px;font-weight:700;line-height:1.3;margin-top:8px;">{title}</div>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:28px;">
                        <p style="margin:0 0 16px;font-size:16px;line-height:1.7;">{greeting}</p>
                        <p style="margin:0 0 18px;font-size:15px;line-height:1.8;">{intro}</p>
                        <div style="background:#f4efe4;border-radius:16px;padding:18px 20px;margin:0 0 20px;">
                          <div style="font-size:13px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#866d45;margin-bottom:10px;">What happens next</div>
                          <ul style="margin:0;padding-left:18px;line-height:1.8;">
                            {bullet_items}
                          </ul>
                        </div>
                        <p style="margin:0 0 16px;font-size:15px;line-height:1.8;">{closing}</p>
                        <p style="margin:0;font-size:15px;line-height:1.8;">Best,<br><strong>{team_name}</strong></p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """.strip()

    def _build_generic_subject(self, department: str, task_request: str, target: Dict[str, object]) -> str:
        meta = self.TEAM_EMAIL_META[department]
        label = target.get("student_code") or target.get("program") or target.get("city") or target.get("name")
        return f"{meta['subject_prefix']} from Masai - {label}"

    def _run_team_email(self, task_request: str, ai_response: str, task_id: str, department: str) -> Dict[str, object]:
        targets = self.db.find_email_targets(department, task_request, limit=5)
        if not targets:
            return {"summary": "No matching contact was found for this email request.", "events": []}

        meta = self.TEAM_EMAIL_META[department]
        ai_summary = self._clean_ai_summary(ai_response, meta["default_summary"])
        sent_count = 0
        queued_count = 0
        failed_count = 0

        for target in targets:
            recipient_label = target.get("student_code") or target.get("name") or target.get("email")
            subject = self._build_generic_subject(department, task_request, target)
            bullets = meta["bullets"]
            body = (
                f"Hi {target['name']},\n\n"
                f"{ai_summary}\n\n"
                "What happens next:\n"
                f"- {bullets[0]}\n"
                f"- {bullets[1]}\n"
                f"- {bullets[2]}\n\n"
                "If you need help, just reply to this email and the team will follow up.\n\n"
                f"Best,\n{meta['team_name']}"
            )
            html_body = self._render_email_html(
                title=subject,
                greeting=f"Hi {target['name']},",
                intro=ai_summary,
                bullets=bullets,
                closing="If you need help, just reply to this email and the team will follow up.",
                team_name=meta["team_name"],
            )
            delivery = self.email_service.deliver(target["email"], subject, body, html_body=html_body)
            self.db.add_email_outbox_entry(
                task_id=task_id,
                department=department,
                recipient_name=target["name"],
                recipient_email=target["email"],
                subject=subject,
                body=body,
                status=delivery["status"],
                delivery_note=delivery["delivery_note"],
                sent_at=delivery["sent_at"],
            )

            if target.get("target_type") == "lead":
                self.db.mark_lead_follow_up(
                    lead_id=target["id"],
                    note=f"{department.title()} email {delivery['status']} for {recipient_label}.",
                    status="outreach_sent",
                )
            else:
                self.db.log_student_communication(
                    student_id=target["id"],
                    note=f"{department.title()} email {delivery['status']} for {recipient_label}.",
                )

            if delivery["status"] == "sent":
                sent_count += 1
            elif delivery["status"] == "failed":
                failed_count += 1
            else:
                queued_count += 1

        return {
            "summary": (
                f"{meta['team_name']} emailed {len(targets)} contact(s). "
                f"Emails: {sent_count} sent, {queued_count} queued, {failed_count} failed."
            ),
            "events": [
                {
                    "actor": f"{department.title()} Automation",
                    "stage": "automation",
                    "message": f"Prepared and sent email communication for {len(targets)} contact(s).",
                },
                {
                    "actor": "Email Outbox",
                    "stage": "email_outbox",
                    "message": f"Email outcomes: {sent_count} sent, {queued_count} queued, {failed_count} failed.",
                },
            ],
        }

    def _run_webinar_follow_up(self, task_request: str, ai_response: str, task_id: str) -> Dict[str, object]:
        city = self._extract_city(task_request)
        leads = self.db.find_webinar_leads(city=city, limit=5)
        if not leads:
            return {"summary": "No webinar leads matched the request, so no email campaign was executed.", "events": []}

        sent_count = 0
        queued_count = 0
        failed_count = 0

        for lead in leads:
            subject = f"Next step for {lead['program']} at Masai"
            ai_summary = self._clean_ai_summary(
                ai_response,
                "We reviewed your webinar attendance and prepared the best next step for your application.",
            )
            bullets = [
                f"Your current track of interest is {lead['program']}.",
                "Our admissions team can help you complete the application in one guided call.",
                "Reply to this email if you want us to reserve a counselor callback slot for you.",
            ]
            body = (
                f"Hi {lead['name']},\n\n"
                f"Thanks for attending the Masai webinar. Based on your interest in {lead['program']}, "
                "we wanted to share the clearest next step for you.\n\n"
                f"{ai_summary}\n\n"
                "What happens next:\n"
                f"- {bullets[0]}\n"
                f"- {bullets[1]}\n"
                f"- {bullets[2]}\n\n"
                "If you'd like, reply to this email and our team will help you finish the application process.\n\n"
                "Best,\nMasai Admissions Team"
            )
            html_body = self._render_email_html(
                title=f"Next step for {lead['program']}",
                greeting=f"Hi {lead['name']},",
                intro=(
                    f"Thanks for attending the Masai webinar. Based on your interest in {lead['program']}, "
                    f"here is the clearest next step for you: {ai_summary}"
                ),
                bullets=bullets,
                closing="If you'd like, reply to this email and our team will help you finish the application process.",
                team_name="Masai Admissions Team",
            )
            delivery = self.email_service.deliver(lead["email"], subject, body, html_body=html_body)
            self.db.add_email_outbox_entry(
                task_id=task_id,
                department="sales",
                recipient_name=lead["name"],
                recipient_email=lead["email"],
                subject=subject,
                body=body,
                status=delivery["status"],
                delivery_note=delivery["delivery_note"],
                sent_at=delivery["sent_at"],
            )
            self.db.mark_lead_follow_up(
                lead_id=lead["id"],
                note=f"Webinar follow-up email {delivery['status']} for {lead['program']}.",
                status="outreach_sent",
            )

            if delivery["status"] == "sent":
                sent_count += 1
            elif delivery["status"] == "failed":
                failed_count += 1
            else:
                queued_count += 1

        return {
            "summary": (
                f"Executed webinar outreach for {len(leads)} leads"
                f"{f' in {city}' if city else ''}. "
                f"Emails: {sent_count} sent, {queued_count} queued, {failed_count} failed."
            ),
            "events": [
                {
                    "actor": "Sales Automation",
                    "stage": "automation",
                    "message": f"Processed {len(leads)} webinar leads and created outbound follow-up emails.",
                },
                {
                    "actor": "Email Outbox",
                    "stage": "email_outbox",
                    "message": f"Email outcomes: {sent_count} sent, {queued_count} queued, {failed_count} failed.",
                },
            ],
        }

    def _run_refund_initiation(self, task_request: str, ai_response: str, task_id: str) -> Dict[str, object]:
        candidate = self.db.find_refund_candidate(task_request)
        if not candidate:
            return {"summary": "No matching learner/payment was found for refund processing.", "events": []}

        refund_amount = self._extract_amount(task_request) or int(candidate["amount_paid"])
        refund_amount = max(0, min(refund_amount, int(candidate["amount_paid"])))
        if refund_amount <= 0:
            return {"summary": "Refund could not be initiated because the learner has no refundable paid amount.", "events": []}

        self.db.apply_refund(
            payment_id=candidate["payment_id"],
            student_email=candidate["email"],
            student_id=candidate["student_id"],
            amount=refund_amount,
            note=f"Refund initiated from founder task. {ai_response[:140]}",
        )
        self.db.add_refund_ledger_entry(
            payment_id=candidate["payment_id"],
            student_email=candidate["email"],
            amount=refund_amount,
            status="initiated",
            reason=task_request[:180],
            note="Refund workflow started by Accounts automation.",
        )

        student_label = f"{candidate['name']} ({candidate.get('student_code') or 'no-code'})"
        subject = f"Refund initiated for {candidate['program']} - {student_label}"
        ai_summary = self._clean_ai_summary(
            ai_response,
            "Your refund request has been approved and moved into processing.",
        )
        bullets = [
            f"Refund initiated amount: INR {refund_amount:,}.",
            "The payment record has been updated in our accounts system.",
            "Reply to this email if you want the transaction reference after processing.",
        ]
        body = (
            f"Hi {candidate['name']},\n\n"
            f"We have initiated your refund for INR {refund_amount:,}. "
            "Our accounts team has updated the payment record and the transfer is now in progress.\n\n"
            f"{ai_summary}\n\n"
            "What happens next:\n"
            f"- {bullets[0]}\n"
            f"- {bullets[1]}\n"
            f"- {bullets[2]}\n\n"
            "If you need the transaction reference, reply to this email and we will share it.\n\n"
            "Best,\nMasai Accounts Team"
        )
        html_body = self._render_email_html(
            title=f"Refund initiated for {candidate['program']}",
            greeting=f"Hi {candidate['name']},",
            intro=(
                f"We have initiated your refund for INR {refund_amount:,}. "
                f"Our accounts team has updated the payment record and the transfer is now in progress. {ai_summary}"
            ),
            bullets=bullets,
            closing="If you need the transaction reference, reply to this email and we will share it.",
            team_name="Masai Accounts Team",
        )
        delivery = self.email_service.deliver(candidate["email"], subject, body, html_body=html_body)
        self.db.add_email_outbox_entry(
            task_id=task_id,
            department="accounts",
            recipient_name=candidate["name"],
            recipient_email=candidate["email"],
            subject=subject,
            body=body,
            status=delivery["status"],
            delivery_note=delivery["delivery_note"],
            sent_at=delivery["sent_at"],
        )

        return {
            "summary": (
                f"Initiated a refund of INR {refund_amount:,} for {student_label} and "
                f"{delivery['status']} the learner notification email."
            ),
            "events": [
                {
                    "actor": "Accounts Automation",
                    "stage": "refund",
                    "message": f"Refund of INR {refund_amount:,} recorded for {student_label} at {candidate['email']}.",
                },
                {
                    "actor": "Email Outbox",
                    "stage": "email_outbox",
                    "message": (
                        f"Refund notification email {delivery['status']} for {student_label} at {candidate['email']}. "
                        f"{delivery['delivery_note']}"
                    ).strip(),
                },
            ],
        }
