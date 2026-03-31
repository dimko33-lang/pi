# π-pipe

**Тестовый стенд матричного умножения для инференса.**

Бенчмарк ядер линейной алгебры для ускорителей ИИ нового поколения. Измеряет пропускную способность умножения матриц на Groq LPU против базового GPU.

Стек: Python + Flask ←→ Groq API (LLM инференс как нагрузка .matmul)

## Установка
```bash
pip install -r requirements.txt
export GROQ_API_KEY=xxx
python server.py
```

**Интерфейс:** `http://localhost:8888`