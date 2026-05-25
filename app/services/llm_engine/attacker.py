import json
import os
import random
import re
from typing import Any, Dict, List

import pandas as pd
from openai import OpenAI

from app.core.config import Settings
from app.services.llm_engine.prompts import (
    ATTACK_INSTRUCTION_TEMPLATE,
    CATEGORY_PROMPTS,
    GOAL_INSTRUCTION_TEMPLATE,
    SCENARIO_EXTRACTION_PROMPT,
    SCENARIO_STAGES,
    STAGE_GUIDELINES,
    USER_ANALYSIS_PROMPT,
)

class AttackerEngine:
    def __init__(self, settings: Settings):
        self.client = OpenAI(
            base_url=settings.llm_studio_base_url,
            api_key=settings.llm_studio_api_key
        )
        self.model_name = settings.llm_studio_model
        
        # CSV 경로 설정 (현재 백엔드 디렉토리 기준)
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        self.file_map = {
            "보이스피싱": os.path.join(self.project_root, "csv/classified_output/보이스피싱.csv"),
            "대출사기": os.path.join(self.project_root, "csv/classified_output/대출사기.csv"),
            "부동산사기": os.path.join(self.project_root, "csv/classified_output/부동산사기.csv"),
            "투자사기": os.path.join(self.project_root, "csv/classified_output/투자사기.csv"),
            "중고거래사기": os.path.join(self.project_root, "csv/classified_output/중고거래사기.csv")
        }
        self.fss_path = os.path.join(self.project_root, "csv/fss_voicephishing_cases_clean.csv")

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                return json.loads(match.group())
            return {}
        except:
            return {}

    def generate_scenario(self, category: str, user_meta: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 카테고리별 특화된 공격 목표와 수단 설정
        category_goals = {
            "보이스피싱": [
                {"goal": "송금 유도", "method": "안전 계좌 이체 또는 공탁금 명목의 직접 송금 요구"},
                {"goal": "악성 앱 설치", "method": "수사기관 사칭 앱(APK) 설치 및 금융정보 탈취 유도"}
            ],
            "대출사기": [
                {"goal": "선입금 편취", "method": "대환대출 승인을 위한 예치금 혹은 수수료 송금 요구"},
                {"goal": "금융 앱 설치", "method": "한도 조회를 가장한 가짜 금융기관 앱 설치 유도"}
            ],
            "중고거래사기": [
                {"goal": "물건 대금 편취", "method": "타 지역 거주를 핑계로 직접 송금 및 택배 거래 유도"},
                {"goal": "안전결제 사기", "method": "네이버페이/번개장터 위장 피싱 링크를 통한 결제 유도"}
            ],
            "투자사기": [
                {"goal": "투자금 편취", "method": "비상장 주식 선취매 혹은 VIP 리딩방 가입비 송금 요구"}
            ],
            "부동산사기": [
                {"goal": "가계약금 편취", "method": "매물 선점을 위한 즉시 이체 종용"}
            ]
        }
        
        goals = category_goals.get(category, category_goals["보이스피싱"])
        selected_goal = random.choice(goals)

        # 2. 카테고리별 정교한 디폴트 시나리오 설정 (계좌번호 추가)
        default_configs = {
            "보이스피싱": {
                "name": "김수현 수사관", "role": "서울중앙지검 수사관", "pretext": "개인정보 도용 사건 연루", "amount": 5000000, "account": "국민은행 403-12-456789 (국가안전보호계좌)"
            },
            "대출사기": {
                "name": "이지훈 대리", "role": "KB국민지원금융 상담원", "pretext": "정부지원 대환대출 특별 선정", "amount": 3000000, "account": "신한은행 110-523-998877 (예치금 수납처)"
            },
            "중고거래사기": {
                "name": "박민수", "role": "개인 판매자", "pretext": "아이패드 프로 급처분", "amount": 450000, "account": "우리은행 1002-888-123456 (박민수)"
            },
            "투자사기": {
                "name": "VIP 리딩팀장", "role": "투자 자산 운용가", "pretext": "상장 예정 비공개 종목 공유", "amount": 10000000, "account": "하나은행 203-910234-55607 (가상자산결제대행)"
            },
            "부동산사기": {
                "name": "김철수 실장", "role": "공인중개사 사무소 실장", "pretext": "역세권 오피스텔 급매물 선점", "amount": 2000000, "account": "농협은행 302-0045-1234-51 (김철수 부동산)"
            }
        }
        
        conf = default_configs.get(category, default_configs["보이스피싱"])

        default_scenario = {
            "official_name": conf["name"],
            "scammer_role": conf["role"],
            "main_goal": selected_goal["goal"],
            "attack_method": selected_goal["method"],
            "pretext": conf["pretext"],
            "logic": "지금 즉시 조치하지 않으면 기회를 상실하거나 법적 불익이 발생할 수 있음",
            "target_amount": conf["amount"],
            "account_no": conf["account"],
            "fake_link": ""
        }

        path = self.file_map.get(category)
        precedent_text = ""
        fss_text = ""

        try:
            if path and os.path.exists(path):
                df_p = pd.read_csv(path)
                valid_p = df_p[df_p['판례내용'].notna()]
                if not valid_p.empty:
                    precedent_text = str(valid_p.sample(n=1).iloc[0]['판례내용'])[:1500]
            
            if os.path.exists(self.fss_path):
                df_f = pd.read_csv(self.fss_path)
                if random.random() > 0.3:
                    match_f = df_f[df_f['content'].str.contains(category[:2], na=False)]
                    if not match_f.empty: 
                        fss_text = str(match_f.sample(n=1).iloc[0]['content'])[:1500]
                if not fss_text:
                    fss_text = str(df_f.sample(n=1).iloc[0]['content'])[:1500]
        except Exception as e:
            print(f"Error loading CSV data: {e}")

        extraction_prompt = SCENARIO_EXTRACTION_PROMPT.format(
            goal=selected_goal['goal'],
            method=selected_goal['method'],
            user_meta=json.dumps(user_meta, ensure_ascii=False),
            precedent_text=(precedent_text if precedent_text else "없음"),
            fss_text=(fss_text if fss_text else "없음")
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=1.0
            )
            data = self._extract_json(response.choices[0].message.content)
            for k, v in data.items():
                if "정보" in str(v) or "미상" in str(v) or not v:
                    data[k] = default_scenario.get(k, v)
            return data
        except:
            return default_scenario

    def analyze_user_state(self, history: List[Dict[str, str]]) -> Dict[str, Any]:
        history_text = "\n".join([f"{h['role']}: {h['content']}" for h in history[-4:]])
        analysis_prompt = USER_ANALYSIS_PROMPT.format(history_text=history_text)
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": analysis_prompt}],
                temperature=0.0
            )
            return self._extract_json(response.choices[0].message.content)
        except:
            return {"compliance": 50, "suspicion": 50, "fear": 50, "is_broke": False}

    def generate_reply(
        self,
        category: str,
        history: List[Dict[str, str]],
        user_meta: Dict[str, Any],
        scenario_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        # 1. 심리 분석
        user_state = self.analyze_user_state(history)
        
        # 2. 단계 결정
        stages = SCENARIO_STAGES.get(category, ["접근", "신뢰형성", "의심대응", "위협_압박", "행동유도", "마무리"])
        
        # 간단한 단계 결정 로직
        user_in = history[-1]['content'] if history and history[-1]['role'] == 'user' else ""
        
        if user_state.get('compliance', 0) > 90 and any(kw in user_in for kw in ["보냈", "송금", "입금", "완료"]):
            current_stage = "마무리"
        elif user_state.get('suspicion', 0) > 85: 
            current_stage = "위협_압박" if "위협_압박" in stages else stages[-2]
        elif user_state.get('compliance', 0) > 80: 
            current_stage = "행동유도" if "행동유도" in stages else stages[-2]
        else:
            idx = min(len(stages)-1, len(history) // 4)
            current_stage = stages[idx]

        stage_guide = STAGE_GUIDELINES.get(current_stage, "")
        base_prompt = CATEGORY_PROMPTS.get(category, "")
        
        goal_instruction = GOAL_INSTRUCTION_TEMPLATE.format(
            main_goal=scenario_data.get('main_goal', '송금 유도'),
            attack_method=scenario_data.get('attack_method', '직접 송금 요구'),
            stage=current_stage,
            logic=scenario_data.get('logic', ''),
            target_amount=scenario_data.get('target_amount', 0),
            account_no=scenario_data.get('account_no', '별도 안내 예정'),
            fake_link=scenario_data.get('fake_link', '')
        )

        instruction = ATTACK_INSTRUCTION_TEMPLATE.format(
            base_prompt=base_prompt,
            goal_instruction=goal_instruction,
            bible_str=json.dumps(scenario_data, ensure_ascii=False),
            scammer_role=scenario_data.get('scammer_role', ''),
            official_name=scenario_data.get('official_name', ''),
            user_meta=json.dumps(user_meta, ensure_ascii=False),
            stage=current_stage,
            stage_guide=stage_guide,
            user_state=json.dumps(user_state, ensure_ascii=False)
        )
        
        messages = [{"role": "system", "content": instruction}] + history[-8:]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.8
            )
            reply = response.choices[0].message.content.strip()
        except:
            reply = "연결이 잠시 끊겼습니다. 다시 말씀해 주시겠어요?"
            
        sanitized_reply = self._sanitize_response(reply)
        
        # 3. 사기 혐의점(is_evidence) 판정 로직
        evidence_stages = ["행동유도", "결제유도", "계약유도", "위협_압박", "재촉_압박", "마무리"]
        is_evidence = (current_stage in evidence_stages) or ("http" in sanitized_reply.lower())

        return {
            "content": sanitized_reply,
            "stage": current_stage,
            "is_evidence": is_evidence
        }

    def _sanitize_response(self, text: str) -> str:
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'[*"\'#~]', '', text)
        text = " ".join(text.split())
        return text
