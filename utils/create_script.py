from openai import OpenAI

def create_script(client, prompt, word, model_name, label='KOR'):
    """프롬프트 + 사용자 입력어(word) → 결과 리스트 반환"""
    prompt = prompt.replace(f"{{LABEL}}", str(label))
    response = client.responses.create(
        model=model_name,
        input=[
            {"role": "developer", "content": prompt},
            {"role": "user", "content": word},
        ],
    )
    return [s.strip() for s in response.output_text.split("\n")]