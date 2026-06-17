-- Adiciona valor 'recalibrar_velocity' ao enum job_type (se ainda não existir)
alter type job_type add value if not exists 'recalibrar_velocity';
