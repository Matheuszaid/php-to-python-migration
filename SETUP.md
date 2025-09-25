# Como testar este projeto

Esse projeto mostra uma migração que fiz de PHP para Python. Basicamente peguei um sistema de billing antigo em PHP e refiz em Python/FastAPI.

## O que você vai encontrar

**Sistema antigo (legacy-php/)**
- PHP puro com MySQL
- Código misturado, sem padrões
- Processamento síncrono (lento)

**Sistema novo (modern-python/)**
- FastAPI com PostgreSQL
- Código organizado em services
- Async/await (bem mais rápido)

## Como rodar

### Sistema PHP (antigo)
```bash
cd legacy-php
docker-compose up
```
Vai rodar em http://localhost:8090

### Sistema Python (novo)
```bash
cd modern-python
docker-compose up
```
Vai rodar em http://localhost:8091

### Ver a diferença de performance
```bash
python3 demo/quick_demo.py
```

Isso vai mostrar a diferença de velocidade entre os dois sistemas.

## O que melhorou

- **Velocidade**: ~15x mais rápido
- **Organização**: Código separado por responsabilidade
- **Banco**: PostgreSQL com relacionamentos corretos
- **Erros**: Tratamento muito melhor
- **Deploy**: Docker containers

## Testando

Para testar as APIs:
- Legacy: http://localhost:8090
- Novo: http://localhost:8091/docs (tem swagger automático)

O banco novo tem constraints e indexes que o antigo não tinha.

---

Se tiver Docker instalado, tudo funciona direto. Senão pode ver o código mesmo que já dá pra entender a diferença.