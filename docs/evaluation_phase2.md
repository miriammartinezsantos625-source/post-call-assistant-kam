# Fase 2 — resultados en 20 notas sintéticas

Modelo: `ollama` / `qwen3.5:9b` · notas procesadas sin error: 20/20

## Alertas

| Alerta | Fuente | Sensibilidad | Especificidad | VP | FN | FP | VN |
|---|---|---|---|---|---|---|---|
| Posible efecto adverso | IA sola | 100 % | 100 % | 3 | 0 | 0 | 17 |
| Posible efecto adverso | Reglas solas | 100 % | 100 % | 3 | 0 | 0 | 17 |
| Posible efecto adverso | IA + reglas | 100 % | 100 % | 3 | 0 | 0 | 17 |
| Pregunta fuera de ficha | IA sola | 100 % | 100 % | 3 | 0 | 0 | 17 |
| Pregunta fuera de ficha | Reglas solas | 100 % | 100 % | 3 | 0 | 0 | 17 |
| Pregunta fuera de ficha | IA + reglas | 100 % | 100 % | 3 | 0 | 0 | 17 |
| Solicitud de información médica | IA sola | 100 % | 93 % | 5 | 0 | 1 | 14 |
| Solicitud de información médica | Reglas solas | 100 % | 100 % | 5 | 0 | 0 | 15 |
| Solicitud de información médica | IA + reglas | 100 % | 93 % | 5 | 0 | 1 | 14 |

## Privacidad

- Identificadores de paciente o nombres de médico en el texto enviado al modelo: **0**
- Sustituciones hechas por el anonimizador: 9 en 5 notas

## Otras métricas

- Conversación detectada correctamente: 20/20
- Tiempo de procesado por nota: mediana 26 s, máximo 35 s
- Campos clave rellenados automáticamente: 78 % de media
- Notas rechazadas por parecer una conversación (nada enviado al modelo): 1

## Discrepancias por nota

- N09 (efecto adverso; datos de paciente): Solicitud de información médica — esperado no, IA sí, reglas no
