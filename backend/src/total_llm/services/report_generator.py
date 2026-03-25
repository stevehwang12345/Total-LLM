#!/usr/bin/env python3
"""
PDF Report Generator

선택한 알람들을 기반으로 보안 보고서를 생성하는 서비스
"""

import asyncpg
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    보안 알람 보고서 생성기

    역할:
    1. 선택한 알람 데이터 조회
    2. QwenVLM을 통한 이미지 분석 (외부 호출)
    3. PDF 보고서 생성
    4. DB에 보고서 메타데이터 저장
    """

    def __init__(
        self,
        db_pool: asyncpg.Pool,
        storage_path: str,
        vlm_analyzer: Optional[Any] = None
    ):
        """
        Args:
            db_pool: asyncpg 연결 풀
            storage_path: PDF 저장 경로
            vlm_analyzer: QwenVLM 이미지 분석기 (선택)
        """
        self.db_pool = db_pool
        self.storage_path = Path(storage_path)
        self.vlm_analyzer = vlm_analyzer

        # 저장 디렉토리 생성
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 한글 폰트 등록 (시스템에 설치된 폰트 사용)
        try:
            # 나눔고딕 폰트 등록 시도
            pdfmetrics.registerFont(TTFont('NanumGothic', '/usr/share/fonts/truetype/nanum/NanumGothic.ttf'))
            self.font_name = 'NanumGothic'
        except:
            logger.warning("⚠️ NanumGothic font not found, using default font")
            self.font_name = 'Helvetica'

        logger.info(f"✅ ReportGenerator initialized (storage={storage_path}, font={self.font_name})")

    # ============================================
    # 보고서 생성 메인
    # ============================================

    async def generate_report(
        self,
        alarm_ids: List[str],
        generated_by: str = "system",
        include_images: bool = True,
        analyze_with_vlm: bool = True
    ) -> Dict[str, Any]:
        """
        보안 알람 보고서 생성

        Args:
            alarm_ids: 보고서에 포함할 알람 ID 리스트
            generated_by: 보고서 생성자 ID
            include_images: 이미지 포함 여부
            analyze_with_vlm: QwenVLM으로 이미지 분석 여부

        Returns:
            {
                "report_id": int,
                "pdf_path": str,
                "total_alarms": int,
                "critical_count": int,
                "file_size_kb": float
            }
        """
        logger.info(f"📄 Generating report for {len(alarm_ids)} alarms...")

        # 1. 알람 데이터 조회
        alarms = await self._fetch_alarms(alarm_ids)

        if not alarms:
            raise ValueError("No alarms found with given IDs")

        # 2. VLM 이미지 분석 (옵션)
        analysis_summary = ""
        if analyze_with_vlm and self.vlm_analyzer:
            analysis_summary = await self._analyze_images_with_vlm(alarms)
        else:
            analysis_summary = self._generate_basic_summary(alarms)

        # 3. PDF 파일 생성
        pdf_path = await self._create_pdf(alarms, analysis_summary, include_images)

        # 4. DB에 보고서 메타데이터 저장
        report_id = await self._save_report_metadata(
            alarm_ids=alarm_ids,
            analysis_summary=analysis_summary,
            pdf_path=pdf_path,
            generated_by=generated_by,
            total_alarms=len(alarms)
        )

        # 5. 알람을 처리됨으로 표시
        await self._mark_alarms_processed(alarm_ids)

        # 파일 크기 계산
        file_size_kb = pdf_path.stat().st_size / 1024

        logger.info(f"✅ Report generated: {report_id} ({file_size_kb:.2f} KB)")

        return {
            "report_id": report_id,
            "pdf_path": str(pdf_path),
            "total_alarms": len(alarms),
            "critical_count": sum(1 for a in alarms if a["severity"] == "CRITICAL"),
            "file_size_kb": file_size_kb
        }

    # ============================================
    # 알람 데이터 조회
    # ============================================

    async def _fetch_alarms(self, alarm_ids: List[str]) -> List[Dict[str, Any]]:
        """DB에서 알람 데이터 조회"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    alarm_id, alarm_type, severity, location, timestamp,
                    image_path, device_id, description
                FROM alarms
                WHERE alarm_id = ANY($1::text[])
                ORDER BY timestamp DESC
                """,
                alarm_ids
            )

            alarms = []
            for row in rows:
                alarms.append({
                    "alarm_id": row["alarm_id"],
                    "alarm_type": row["alarm_type"],
                    "severity": row["severity"],
                    "location": row["location"],
                    "timestamp": row["timestamp"],
                    "image_path": row["image_path"],
                    "device_id": row["device_id"],
                    "description": row["description"]
                })

            return alarms

    # ============================================
    # VLM 이미지 분석
    # ============================================

    async def _analyze_images_with_vlm(self, alarms: List[Dict[str, Any]]) -> str:
        """
        QwenVLM으로 알람 이미지 분석 (병렬 처리)

        Args:
            alarms: 알람 리스트

        Returns:
            종합 분석 요약 텍스트
        """
        if not self.vlm_analyzer:
            return self._generate_basic_summary(alarms)

        logger.info(f"🔍 Analyzing {len(alarms)} images with QwenVLM (batch mode)...")

        # 이미지가 있는 알람만 필터링
        alarms_with_images = [
            alarm for alarm in alarms
            if alarm.get("image_path") and Path(alarm["image_path"]).exists()
        ]

        if not alarms_with_images:
            logger.warning("⚠️ No valid images found, using basic summary")
            return self._generate_basic_summary(alarms)

        # 병렬 배치 분석
        try:
            analyses = await self.vlm_analyzer.analyze_batch(
                images=[
                    {
                        "image_path": alarm["image_path"],
                        "alarm_type": alarm["alarm_type"],
                        "location": alarm["location"],
                        "severity": alarm["severity"]
                    }
                    for alarm in alarms_with_images
                ],
                max_concurrent=5
            )

            # 분석 결과를 alarm_id와 매핑
            analysis_results = []
            for i, alarm in enumerate(alarms_with_images):
                if i < len(analyses):
                    analysis_results.append({
                        "alarm_id": alarm["alarm_id"],
                        "location": alarm["location"],
                        "alarm_type": alarm["alarm_type"],
                        "severity": alarm["severity"],
                        "timestamp": alarm["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                        "analysis": analyses[i]
                    })

            # 종합 요약 생성
            summary = self._generate_vlm_summary(analysis_results, alarms)
            return summary

        except Exception as e:
            logger.error(f"❌ VLM batch analysis failed: {e}")
            return self._generate_basic_summary(alarms)

    def _generate_vlm_summary(
        self,
        analysis_results: List[Dict[str, Any]],
        all_alarms: List[Dict[str, Any]]
    ) -> str:
        """
        VLM 분석 결과를 기반으로 종합 요약 생성

        Args:
            analysis_results: VLM 분석 결과 리스트
            all_alarms: 전체 알람 리스트 (통계용)

        Returns:
            종합 요약 텍스트
        """
        # 기본 통계
        total = len(all_alarms)
        analyzed = len(analysis_results)
        critical = sum(1 for a in all_alarms if a["severity"] == "CRITICAL")
        high = sum(1 for a in all_alarms if a["severity"] == "HIGH")

        # 위협 탐지 통계
        threats_detected = sum(
            1 for r in analysis_results
            if r["analysis"].get("threat_detected", False)
        )
        critical_threats = sum(
            1 for r in analysis_results
            if r["analysis"].get("threat_level") in ["CRITICAL", "HIGH"]
        )

        # 시간 범위
        timestamps = [a["timestamp"] for a in all_alarms]
        start_time = min(timestamps)
        end_time = max(timestamps)

        # 주요 위협 목록 (최대 5개)
        top_threats = []
        for result in analysis_results:
            if result["analysis"].get("threat_detected"):
                top_threats.append({
                    "location": result["location"],
                    "type": result["alarm_type"],
                    "level": result["analysis"].get("threat_level", "UNKNOWN"),
                    "description": result["analysis"].get("description", ""),
                    "timestamp": result["timestamp"]
                })

        # 심각도순 정렬
        threat_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        top_threats.sort(key=lambda x: threat_order.get(x["level"], 4))
        top_threats = top_threats[:5]

        # 요약 생성
        summary = f"""보안 알람 AI 분석 보고서

[분석 기간]
- 시작: {start_time.strftime("%Y-%m-%d %H:%M:%S")}
- 종료: {end_time.strftime("%Y-%m-%d %H:%M:%S")}

[분석 통계]
- 전체 알람: {total}건
- AI 이미지 분석: {analyzed}건
- 위협 탐지: {threats_detected}건 ({threats_detected/analyzed*100:.1f}%)
- 심각한 위협: {critical_threats}건

[심각도 분포]
- CRITICAL: {critical}건
- HIGH: {high}건

[주요 위협 사항]
"""

        if top_threats:
            for i, threat in enumerate(top_threats, 1):
                summary += f"""{i}. [{threat['level']}] {threat['location']}
   - 유형: {threat['type']}
   - 시각: {threat['timestamp']}
   - 상세: {threat['description'][:100]}

"""
        else:
            summary += "- 심각한 위협이 탐지되지 않았습니다.\n\n"

        # 권고 사항 종합
        all_recommendations = set()
        for result in analysis_results:
            recommendations = result["analysis"].get("recommended_actions", [])
            all_recommendations.update(recommendations[:3])  # 각 알람당 최대 3개

        if all_recommendations:
            summary += "[AI 권고 사항]\n"
            for i, recommendation in enumerate(list(all_recommendations)[:5], 1):
                summary += f"{i}. {recommendation}\n"
        else:
            summary += "[권고 사항]\n"
            summary += "- 정기적인 보안 점검 및 모니터링을 지속하시기 바랍니다.\n"

        return summary

    def _generate_basic_summary(self, alarms: List[Dict[str, Any]]) -> str:
        """기본 통계 기반 요약"""
        total = len(alarms)
        critical = sum(1 for a in alarms if a["severity"] == "CRITICAL")
        high = sum(1 for a in alarms if a["severity"] == "HIGH")
        medium = sum(1 for a in alarms if a["severity"] == "MEDIUM")

        # 시간 범위
        timestamps = [a["timestamp"] for a in alarms]
        start_time = min(timestamps)
        end_time = max(timestamps)

        summary = f"""보안 알람 분석 보고서

[기간]
- 시작: {start_time.strftime("%Y-%m-%d %H:%M:%S")}
- 종료: {end_time.strftime("%Y-%m-%d %H:%M:%S")}

[통계]
- 전체 알람: {total}건
- 심각도 분포:
  * CRITICAL: {critical}건
  * HIGH: {high}건
  * MEDIUM: {medium}건

[주요 위치]
{self._get_top_locations(alarms, 5)}

[권고 사항]
- 심각도가 높은 알람에 대한 즉각적인 대응이 필요합니다.
- 반복적으로 발생하는 위치에 대한 보안 강화를 권장합니다.
"""
        return summary

    def _get_top_locations(self, alarms: List[Dict[str, Any]], top_n: int = 5) -> str:
        """빈도가 높은 위치 추출"""
        from collections import Counter

        locations = [a["location"] for a in alarms]
        top_locations = Counter(locations).most_common(top_n)

        result = ""
        for location, count in top_locations:
            result += f"- {location}: {count}건\n"

        return result

    # ============================================
    # PDF 생성
    # ============================================

    async def _create_pdf(
        self,
        alarms: List[Dict[str, Any]],
        analysis_summary: str,
        include_images: bool
    ) -> Path:
        """
        PDF 파일 생성

        Args:
            alarms: 알람 리스트
            analysis_summary: 분석 요약
            include_images: 이미지 포함 여부

        Returns:
            생성된 PDF 파일 경로
        """
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"security_report_{timestamp}.pdf"
        pdf_path = self.storage_path / filename

        # PDF 문서 생성
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )

        # 스타일 정의
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontName=self.font_name,
            fontSize=18,
            spaceAfter=12
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontName=self.font_name,
            fontSize=14,
            spaceAfter=6
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontName=self.font_name,
            fontSize=10,
            spaceAfter=6
        )

        # 문서 내용 생성
        story = []

        # 제목
        story.append(Paragraph("보안 알람 분석 보고서", title_style))
        story.append(Spacer(1, 0.5*cm))

        # 생성 일시
        story.append(Paragraph(f"생성 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
        story.append(Spacer(1, 0.3*cm))

        # 분석 요약
        story.append(Paragraph("종합 분석", heading_style))
        for line in analysis_summary.split('\n'):
            if line.strip():
                story.append(Paragraph(line, normal_style))
        story.append(Spacer(1, 0.5*cm))

        # 알람 상세 (표 형식)
        story.append(Paragraph("알람 상세 내역", heading_style))
        story.append(Spacer(1, 0.3*cm))

        # 표 데이터
        table_data = [["시간", "심각도", "위치", "유형", "설명"]]
        for alarm in alarms:
            table_data.append([
                alarm["timestamp"].strftime("%m/%d %H:%M"),
                alarm["severity"],
                alarm["location"],
                alarm["alarm_type"],
                alarm.get("description", "")[:30]  # 30자 제한
            ])

        # 표 스타일
        table = Table(table_data, colWidths=[3*cm, 2*cm, 4*cm, 3.5*cm, 4.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        story.append(table)
        story.append(Spacer(1, 0.5*cm))

        # 이미지 포함
        if include_images:
            story.append(PageBreak())
            story.append(Paragraph("알람 이미지", heading_style))
            story.append(Spacer(1, 0.3*cm))

            for alarm in alarms:
                if alarm.get("image_path"):
                    image_path = Path(alarm["image_path"])
                    if image_path.exists():
                        try:
                            story.append(Paragraph(
                                f"{alarm['alarm_id']} - {alarm['location']} ({alarm['timestamp'].strftime('%Y-%m-%d %H:%M')})",
                                normal_style
                            ))
                            img = Image(str(image_path), width=12*cm, height=9*cm)
                            story.append(img)
                            story.append(Spacer(1, 0.5*cm))
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to add image {image_path}: {e}")

        # PDF 빌드
        doc.build(story)

        logger.info(f"✅ PDF created: {pdf_path}")
        return pdf_path

    # ============================================
    # DB 메타데이터 저장
    # ============================================

    async def _save_report_metadata(
        self,
        alarm_ids: List[str],
        analysis_summary: str,
        pdf_path: Path,
        generated_by: str,
        total_alarms: int
    ) -> int:
        """보고서 메타데이터를 DB에 저장"""
        critical_count = 0

        # Critical 알람 개수 계산
        async with self.db_pool.acquire() as conn:
            critical_count = await conn.fetchval(
                """
                SELECT COUNT(*)
                FROM alarms
                WHERE alarm_id = ANY($1::text[]) AND severity = 'CRITICAL'
                """,
                alarm_ids
            )

            # 보고서 저장
            report_id = await conn.fetchval(
                """
                INSERT INTO reports (
                    alarm_ids, analysis_summary, pdf_path, generated_by,
                    total_alarms, critical_count, generated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING report_id
                """,
                alarm_ids, analysis_summary, str(pdf_path), generated_by,
                total_alarms, critical_count, datetime.now()
            )

        return report_id

    async def _mark_alarms_processed(self, alarm_ids: List[str]) -> None:
        """보고서에 포함된 알람을 처리됨으로 표시"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE alarms
                SET is_processed = TRUE, updated_at = $2
                WHERE alarm_id = ANY($1::text[])
                """,
                alarm_ids, datetime.now()
            )
