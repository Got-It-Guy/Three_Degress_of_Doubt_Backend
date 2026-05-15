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
            "보이스피싱": os.path.join(self.project_root, "csv/classified_output/보이스피싱.csv"),
            "대출사기": os.path.join(self.project_root, "csv/classified_output/대출사기.csv"),
            "부동산사기": os.path.join(self.project_root, "csv/classified_output/부동산사기.csv"),
            "투자사기": os.path.join(self.project_root, "csv/classified_output/투자사기.csv")
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
        attack_goals = [
            {"goal": "송금 유도", "method": "안전 계좌 이체 또는 공탁금 명목의 직접 송금 요구"},
            {"goal": "악성 앱 설치", "method": "원격 제어 앱(TeamViewer 등) 또는 수사기관 사칭 앱 설치 유도"},
            {"goal": "피싱 사이트 유도", "method": "가짜 검찰청/은행 사이트 접속 및 금융정보(비밀번호, OTP) 입력 유도"}
        ]
        selected_goal = random.choice(attack_goals)

        default_scenario = {
            "official_name": "김수현 수사관", 
            "scammer_role": "수사관",
            "main_goal": selected_goal["goal"],
            "attack_method": selected_goal["method"],
            "pretext": "명의도용 및 자금세탁",
            "logic": "본인 계좌가 대포통장으로 이용되어 긴급 확인이 필요함",
            "target_amount": 5000000,
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
    ) -> str:
        # 1. 심리 분석
        user_state = self.analyze_user_state(history)
        
        # 2. 단계 결정
        stages = SCENARIO_STAGES.get(category, ["접근", "신뢰형성", "의심대응", "위협_압박", "행동유도", "마무리"])
        
        # 간단한 단계 결정 로직 (prototype과 동일)
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
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.8
        )
        
        reply = response.choices[0].message.content.strip()
        return self._sanitize_response(reply)

    def _sanitize_response(self, text: str) -> str:
        text = re.sub(r'\(.*?\)', '', text)
        text = re.sub(r'[*"\'#~]', '', text)
        text = " ".join(text.split())
        return text
