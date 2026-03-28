import os
import json
import logging
from typing import List, Dict, Any, Optional
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class AITagger:
    def __init__(self):
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        
        if self.openai_key and OpenAI is not None:
            self.openai_client = OpenAI(api_key=self.openai_key)
            logger.info("AITagger initialized with OpenAI")
        elif self.gemini_key:
            genai.configure(api_key=self.gemini_key)
            self.gemini_model = genai.GenerativeModel('gemini-pro')
            logger.info("AITagger initialized with Gemini")
        else:
            logger.warning("No AI API key found. AITagger will use MOCK mode for tagging.")

    def get_tagging_prompt(self, statement: str, solution: str) -> str:
        return f"""
Ești un expert în educație și matematică. Analizează următorul exercițiu și soluția sa pentru a extrage etichete (tags) relevante.

EXERCIȚIU:
{statement}

SOLUȚIE:
{solution}

Cerințe:
1. Returnează un obiect JSON care conține o listă de etichete sub cheia 'tags'.
2. Fiecare etichetă trebuie să aibă următoarele câmpuri:
   - 'namespace': una din: 'topic', 'subtopic', 'skill', 'method', 'difficulty', 'difficulty_math', 'difficulty_time'
   - 'key': un identificator unic (slug) în română fără spații (ex: 'algebra', 'ecuatii-grad-2')
   - 'label': un nume prietenos în română (ex: 'Algebră', 'Ecuații de gradul II')
   - 'weight': un număr între 0 și 1 care indică relevanța etichetei

3. Namespace-uri:
   - 'topic': tema principală (algebra, analiza, geometrie, trigonometrie, probabilitati)
   - 'subtopic': sub-tema (ecuatii-grad-2, functii-continue, matrice, etc.)
   - 'skill': competența necesară (calcul-algebric, demonstratie, rezolvare-ecuatii, etc.)
   - 'method': metoda de rezolvare (inductie, reducere-la-absurd, substitutie, integrare-parti, etc.)
   - 'difficulty': nivel calitativ (usor, mediu, greu)
   - 'difficulty_math': complexitate matematică (simplu, moderat, complex, avansat)
   - 'difficulty_time': timp estimat (rapid, mediu, lung)

4. NU genera tag-uri de poziție (subiect, exercise, subpoint, path) — alea se generează automat la import.

Exemplu de format JSON:
{{
  "tags": [
    {{ "namespace": "topic", "key": "analiza", "label": "Analiză matematică", "weight": 1.0 }},
    {{ "namespace": "subtopic", "key": "derivate", "label": "Derivate", "weight": 1.0 }},
    {{ "namespace": "skill", "key": "calcul-derivate", "label": "Calcul de derivate", "weight": 0.9 }},
    {{ "namespace": "method", "key": "regula-derivarii", "label": "Regula de derivare", "weight": 0.8 }},
    {{ "namespace": "difficulty", "key": "mediu", "label": "Mediu", "weight": 1.0 }},
    {{ "namespace": "difficulty_math", "key": "moderat", "label": "Moderat", "weight": 1.0 }},
    {{ "namespace": "difficulty_time", "key": "mediu", "label": "Mediu", "weight": 1.0 }}
  ]
}}

Returnează DOAR JSON-ul, fără alte explicații.
"""

    def tag_exercise(self, statement: str, solution: str) -> List[Dict[str, Any]]:
        if not statement:
            return []
            
        if not self.openai_key and not self.gemini_key:
            return self._mock_tagging(statement)

        prompt = self.get_tagging_prompt(statement, solution or "")
        
        try:
            if self.openai_key:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"}
                )
                result_text = response.choices[0].message.content
            else: # Gemini
                response = self.gemini_model.generate_content(prompt)
                result_text = response.text
                # Uneori Gemini pune blockuri de code markdown
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0]
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0]

            data = json.loads(result_text)
            return data.get("tags", [])
            
        except Exception as e:
            logger.error(f"Error during AI tagging: {e}")
            return self._mock_tagging(statement)

    def _mock_tagging(self, statement: str) -> List[Dict[str, Any]]:
        """Mock implementation for testing when no API keys are available."""
        tags = [
            {"namespace": "topic", "key": "matematica", "label": "Matematică", "weight": 1.0}
        ]
        
        statement_lower = statement.lower()
        if "ecuati" in statement_lower or "ecuați" in statement_lower:
            tags.append({"namespace": "subtopic", "key": "ecuatii", "label": "Ecuații", "weight": 0.9})
        if "funcț" in statement_lower or "funct" in statement_lower:
            tags.append({"namespace": "subtopic", "key": "functii", "label": "Funcții", "weight": 0.9})
        if "triun" in statement_lower:
            tags.append({"namespace": "subtopic", "key": "geometrie-triunghi", "label": "Geometrie - Triunghi", "weight": 0.9})
            
        return tags

_tagger_instance = None

def get_ai_tagger() -> AITagger:
    global _tagger_instance
    if _tagger_instance is None:
        _tagger_instance = AITagger()
    return _tagger_instance
