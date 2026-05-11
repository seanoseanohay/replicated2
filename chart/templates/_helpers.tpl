{{- define "bundle-analyzer.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "bundle-analyzer.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "bundle-analyzer.name" . -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "bundle-analyzer.labels" -}}
app.kubernetes.io/name: {{ include "bundle-analyzer.name" . }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "bundle-analyzer.selectorLabels" -}}
app.kubernetes.io/name: {{ include "bundle-analyzer.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "bundle-analyzer.postgresName" -}}
{{ include "bundle-analyzer.fullname" . }}-postgresql
{{- end -}}

{{- define "bundle-analyzer.redisName" -}}
{{ include "bundle-analyzer.fullname" . }}-redis-master
{{- end -}}

{{- define "bundle-analyzer.databaseUrl" -}}
{{- if .Values.postgresql.enabled -}}
postgresql+asyncpg://{{ .Values.postgresql.auth.username }}:{{ .Values.postgresql.auth.password }}@{{ include "bundle-analyzer.postgresName" . }}:5432/{{ .Values.postgresql.auth.database }}
{{- else -}}
{{- if or (not .Values.externalPostgresql.host) (not .Values.externalPostgresql.username) (not .Values.externalPostgresql.password) (not .Values.externalPostgresql.database) -}}
{{- fail "externalPostgresql.host, username, password, and database are required when postgresql.enabled=false" -}}
{{- end -}}
postgresql+asyncpg://{{ .Values.externalPostgresql.username }}:{{ .Values.externalPostgresql.password }}@{{ .Values.externalPostgresql.host }}:{{ .Values.externalPostgresql.port }}/{{ .Values.externalPostgresql.database }}
{{- end -}}
{{- end -}}

{{- define "bundle-analyzer.postgresHost" -}}
{{- if .Values.postgresql.enabled -}}
{{ include "bundle-analyzer.postgresName" . }}
{{- else -}}
{{ .Values.externalPostgresql.host }}
{{- end -}}
{{- end -}}

{{- define "bundle-analyzer.postgresPort" -}}
{{- if .Values.postgresql.enabled -}}
5432
{{- else -}}
{{ .Values.externalPostgresql.port }}
{{- end -}}
{{- end -}}

{{- define "bundle-analyzer.redisUrl" -}}
redis://{{ include "bundle-analyzer.redisName" . }}:6379/0
{{- end -}}

{{- define "bundle-analyzer.minioName" -}}
{{ include "bundle-analyzer.fullname" . }}-minio
{{- end -}}

{{- define "bundle-analyzer.image" -}}
{{- $global := index . 0 -}}
{{- $repo := index . 1 -}}
{{- $tag := index . 2 -}}
{{- $registry := $global.proxyRegistry | default "" -}}
{{- if $registry -}}{{ $registry }}/{{ end -}}{{ $repo }}:{{ $tag }}
{{- end -}}

{{- define "bundle-analyzer.imagePullSecrets" -}}
{{- if and .Values.global.replicated .Values.global.replicated.dockerconfigjson }}
imagePullSecrets:
  - name: enterprise-pull-secret
{{- end }}
{{- end -}}
