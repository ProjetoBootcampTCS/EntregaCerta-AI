-- Tabelas isoladas das bases Olist e dos experimentos de ML.
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY,
    nome TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK (perfil IN ('cliente', 'analista')),
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sessoes (
    token_hash TEXT PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    csrf TEXT NOT NULL,
    expira_em TIMESTAMPTZ NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sessoes_expiracao ON sessoes(expira_em);
CREATE TABLE IF NOT EXISTS limites_acesso (
    chave TEXT PRIMARY KEY,
    quantidade INTEGER NOT NULL,
    reinicia_em TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS pedidos_demo (
    id UUID PRIMARY KEY,
    cliente_id UUID NOT NULL REFERENCES usuarios(id),
    chave_requisicao UUID NOT NULL,
    assinatura TEXT NOT NULL,
    itens JSONB NOT NULL,
    uf TEXT NOT NULL CHECK (length(uf) = 2),
    total_centavos INTEGER NOT NULL CHECK (total_centavos > 0),
    status TEXT NOT NULL DEFAULT 'recebido' CHECK (status IN ('recebido', 'em_preparacao', 'despachado', 'entregue')),
    eventos JSONB NOT NULL,
    origem TEXT NOT NULL DEFAULT 'demonstracao_loja' CHECK (origem = 'demonstracao_loja'),
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(cliente_id, chave_requisicao)
);
CREATE INDEX IF NOT EXISTS pedidos_demo_cliente ON pedidos_demo(cliente_id, criado_em DESC);

-- Migração aditiva e repetível: pedidos antigos continuam sem prazo/responsável.
ALTER TABLE pedidos_demo ADD COLUMN IF NOT EXISTS prazo_prometido DATE;
ALTER TABLE pedidos_demo ADD COLUMN IF NOT EXISTS prazo_original DATE;
ALTER TABLE pedidos_demo ADD COLUMN IF NOT EXISTS responsavel_id UUID REFERENCES usuarios(id);
ALTER TABLE pedidos_demo ADD COLUMN IF NOT EXISTS versao INTEGER NOT NULL DEFAULT 1;
ALTER TABLE pedidos_demo ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMPTZ;

-- Feedback explícito do assistente, independente das tabelas e alvos de ML.
CREATE TABLE IF NOT EXISTS assistente_feedback (
    resposta_id UUID PRIMARY KEY,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    avaliacao SMALLINT NOT NULL CHECK (avaliacao IN (-1,1)),
    categoria TEXT CHECK (categoria IN ('incorreta','confusa','nao_respondeu','outro')),
    pergunta TEXT NOT NULL,
    resposta TEXT NOT NULL,
    contexto TEXT NOT NULL CHECK (contexto IN ('geral','loja','olist')),
    modelo TEXT NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
