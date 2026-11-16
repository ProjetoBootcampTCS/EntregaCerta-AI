CREATE OR REPLACE VIEW public.vw_pedidos_inferencia AS
SELECT p.order_id,
    p.particao,
    (p.order_approved_at)::timestamp without time zone AS order_approved_at,
    NULLIF(c.customer_state, 'NAO_INFORMADO'::text) AS customer_state,
    NULLIF(l.uf_origem, 'NAO_INFORMADO'::text) AS uf_origem,
    NULLIF(l.categoria_principal, 'NAO_INFORMADO'::text) AS categoria_principal,
    (l.quantidade_itens)::double precision AS quantidade_itens,
    (l.quantidade_produtos)::double precision AS quantidade_produtos,
    (l.quantidade_vendedores)::double precision AS quantidade_vendedores,
    (l.quantidade_categorias)::double precision AS quantidade_categorias,
    (l.quantidade_ufs_origem)::double precision AS quantidade_ufs_origem,
    (l.valor_itens)::double precision AS valor_itens,
    (l.valor_frete)::double precision AS valor_frete,
        CASE
            WHEN ((q.faltante_peso_total_g)::numeric = (1)::numeric) THEN NULL::double precision
            ELSE (l.peso_total_g)::double precision
        END AS peso_total_g,
        CASE
            WHEN ((q.faltante_volume_total_cm3)::numeric = (1)::numeric) THEN NULL::double precision
            ELSE (l.volume_total_cm3)::double precision
        END AS volume_total_cm3,
    (l.itens_sem_peso)::double precision AS itens_sem_peso,
    (l.itens_sem_dimensoes)::double precision AS itens_sem_dimensoes,
    (l.itens_sem_categoria)::double precision AS itens_sem_categoria,
        CASE
            WHEN ((q.faltante_distancia_media_vendedores_km)::numeric = (1)::numeric) THEN NULL::double precision
            ELSE (l.distancia_media_vendedores_km)::double precision
        END AS distancia_media_vendedores_km,
        CASE
            WHEN ((q.faltante_distancia_max_vendedores_km)::numeric = (1)::numeric) THEN NULL::double precision
            ELSE (l.distancia_max_vendedores_km)::double precision
        END AS distancia_max_vendedores_km,
    (l.vendedores_sem_distancia)::double precision AS vendedores_sem_distancia,
    (l.vendedores_sem_uf)::double precision AS vendedores_sem_uf,
        CASE
            WHEN ((q.faltante_valor_pago)::numeric = (1)::numeric) THEN NULL::double precision
            ELSE (g.valor_pago)::double precision
        END AS valor_pago,
        CASE
            WHEN ((q.faltante_quantidade_pagamentos)::numeric = (1)::numeric) THEN NULL::double precision
            ELSE (g.quantidade_pagamentos)::double precision
        END AS quantidade_pagamentos,
        CASE
            WHEN ((q.faltante_quantidade_formas_pagamento)::numeric = (1)::numeric) THEN NULL::double precision
            ELSE (g.quantidade_formas_pagamento)::double precision
        END AS quantidade_formas_pagamento,
        CASE
            WHEN ((q.faltante_parcelas_maximas)::numeric = (1)::numeric) THEN NULL::double precision
            ELSE (g.parcelas_maximas)::double precision
        END AS parcelas_maximas,
    NULLIF(g.tipo_pagamento_principal, 'NAO_INFORMADO'::text) AS tipo_pagamento_principal,
    (l.prazo_prometido_dias)::double precision AS prazo_prometido_dias,
    (l.tempo_aprovacao_horas)::double precision AS tempo_aprovacao_horas,
    (l.dia_semana_aprovacao)::double precision AS dia_semana_aprovacao,
    (l.mes_aprovacao)::double precision AS mes_aprovacao,
    (l.hora_aprovacao)::double precision AS hora_aprovacao
   FROM ((((pedidos p
     JOIN clientes c USING (pedido_id))
     JOIN logistica l USING (pedido_id))
     JOIN pagamentos g USING (pedido_id))
     JOIN qualidade_dados q USING (pedido_id));
