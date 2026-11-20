import { useState, useEffect, useCallback } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import PropTypes from 'prop-types'
import { settingsApi } from '../../services/api'
import RealtimeStatusBadge from '../layout/RealtimeStatusBadge'

const MANAGED_KEYS = ['TOSS_CLIENT_ID', 'TOSS_CLIENT_SECRET', 'NAVER_CLIENT_ID', 'NAVER_CLIENT_SECRET']
// 응답에 없는 키도 빈 문자열로 채워 입력란을 항상 제어 컴포넌트로 유지한다.
const EMPTY_KEYS = Object.fromEntries(MANAGED_KEYS.map((key) => [key, '']))

/**
 * API 키 설정 패널 컴포넌트
 * 토스증권 Open API(실시간 시세)와 NAVER API HUB(뉴스) 키를 입력하고 저장한다.
 * 토스 키는 예전엔 .env를 직접 고쳐야만 넣을 수 있어, 데스크톱 앱 사용자가 키 없이
 * 실시간 시세가 꺼진 채로 쓰는 일이 있었다. 저장하면 앱 재시작 없이 바로 재연결된다.
 */
function ConfiguredBadge({ ok }) {
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
        ok
          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
          : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      }`}
    >
      {ok ? '설정됨' : '미설정'}
    </span>
  )
}

ConfiguredBadge.propTypes = { ok: PropTypes.bool }

export default function ApiKeysPanel() {
  const queryClient = useQueryClient()
  const [keys, setKeys] = useState(EMPTY_KEYS)
  const [configured, setConfigured] = useState({ naver: false, toss: false })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState(null)
  const [editing, setEditing] = useState(false)

  const fetchKeys = useCallback(async () => {
    try {
      setLoading(true)
      const response = await settingsApi.getApiKeys()
      setKeys({ ...EMPTY_KEYS, ...response.data.keys })
      setConfigured(response.data.configured)
    } catch (err) {
      console.error('Failed to fetch API keys:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchKeys()
  }, [fetchKeys])

  const handleSave = async () => {
    try {
      setSaving(true)
      setMessage(null)

      // 마스킹된 값(*)은 바꾸지 않은 것으로 보고 보내지 않는다(토스 Secret은 수정 화면에서도
      // 마스킹돼 내려오므로, 새 값을 입력했을 때만 저장된다).
      const payload = {}
      for (const key of MANAGED_KEYS) {
        const value = keys[key]?.trim()
        if (value && !value.includes('*')) payload[key] = value
      }
      if (Object.keys(payload).length === 0) {
        setMessage({ type: 'warning', text: '변경된 값이 없습니다. 새 값을 입력해주세요.' })
        return
      }

      await settingsApi.updateApiKeys(payload)
      const tossChanged = 'TOSS_CLIENT_ID' in payload || 'TOSS_CLIENT_SECRET' in payload
      setMessage({
        type: 'success',
        text: tossChanged ? 'API 키가 저장되었습니다. 토스 실시간 시세에 다시 연결합니다.' : 'API 키가 저장되었습니다.',
      })
      if (tossChanged) {
        // 재연결 결과(연결됨·인증 실패)가 상태 배지에 곧바로 반영되도록 몇 초 뒤 다시 조회한다.
        setTimeout(() => queryClient.invalidateQueries({ queryKey: ['realtime-status'] }), 3000)
      }
      setEditing(false)
      // 저장 후 마스킹된 값으로 다시 로드
      await fetchKeys()
    } catch (err) {
      setMessage({ type: 'error', text: `저장 실패: ${err.message}` })
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = async () => {
    setEditing(true)
    setMessage(null)
    try {
      const response = await settingsApi.getApiKeys(true)
      setKeys({ ...EMPTY_KEYS, ...response.data.keys })
    } catch (err) {
      console.error('Failed to fetch raw API keys:', err)
    }
  }

  const handleCancel = () => {
    setEditing(false)
    setMessage(null)
    fetchKeys()
  }

  if (loading) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900 p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/4"></div>
          <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
          <div className="h-10 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow dark:shadow-gray-900">
      {/* 헤더 */}
      <div className="px-4 sm:px-6 py-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-lg sm:text-xl font-semibold text-gray-900 dark:text-gray-100">
              API 키 설정
            </h2>
            <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 mt-1">
              실시간 시세(토스증권 Open API)와 뉴스 수집(NAVER API HUB) 키를 설정합니다
            </p>
          </div>
        </div>
      </div>

      {/* 설정 내용 */}
      <div className="px-4 sm:px-6 py-6 space-y-6">
        {/* 토스증권 Open API 키 섹션 */}
        <section>
          <div className="flex flex-wrap items-center gap-2 mb-2">
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              토스증권 Open API (실시간 시세)
            </h3>
            <ConfiguredBadge ok={configured.toss} />
            <RealtimeStatusBadge />
          </div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
            현재가·등락률·지수를 실시간으로 받습니다. 키가 없으면 실시간 시세 없이 네이버 수집 데이터만 표시됩니다.
            토스증권 Open API 콘솔에서 발급한 Client ID/Secret을 입력하세요
            (<a href="https://openapi.tossinvest.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 hover:underline">발급 안내</a>).
            같은 키를 쓰는 다른 프로그램(개발 서버 등)과 동시에 켜면 서로 연결이 끊길 수 있습니다.
          </p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Client ID</label>
              <input
                type="text"
                value={keys.TOSS_CLIENT_ID}
                onChange={(e) => setKeys({ ...keys, TOSS_CLIENT_ID: e.target.value })}
                disabled={!editing}
                placeholder={editing ? 'tsck_로 시작하는 Client ID' : ''}
                aria-label="토스 Client ID"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:bg-gray-50 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-400 font-mono"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Client Secret</label>
              <input
                type="password"
                value={keys.TOSS_CLIENT_SECRET}
                onChange={(e) => setKeys({ ...keys, TOSS_CLIENT_SECRET: e.target.value })}
                onFocus={() => {
                  // 저장된 Secret은 마스킹돼 내려온다 — 바꾸려면 새 값을 처음부터 입력한다.
                  if (editing && keys.TOSS_CLIENT_SECRET.includes('*')) setKeys({ ...keys, TOSS_CLIENT_SECRET: '' })
                }}
                disabled={!editing}
                placeholder={editing ? '바꿀 때만 새 Secret 입력 (비워 두면 유지)' : ''}
                aria-label="토스 Client Secret"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:bg-gray-50 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-400 font-mono"
              />
            </div>
          </div>
        </section>

        {/* 안내 메시지 */}
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <div className="flex">
            <svg className="w-5 h-5 text-blue-400 mt-0.5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div className="text-sm text-blue-700 dark:text-blue-300">
              <p className="font-medium mb-1">NAVER API HUB 검색 API</p>
              <p>
                뉴스 수집 기능을 사용하려면 네이버 클라우드 플랫폼 콘솔의 NAVER API HUB에서
                Application을 등록하고 인증 정보(Client ID/Secret)를 발급받아야 합니다.
                기존 네이버 개발자 센터 키는 사용할 수 없습니다.
              </p>
              <a
                href="https://api.ncloud-docs.com/docs/naver-api-hub-overview"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center mt-2 text-blue-600 dark:text-blue-400 hover:underline font-medium"
              >
                NAVER API HUB 발급 안내
                <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
          </div>
        </div>

        {/* 네이버 API 키 섹션 */}
        <section>
          <div className="flex items-center gap-2 mb-4">
            <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100">
              NAVER API HUB 검색 API (뉴스)
            </h3>
            <ConfiguredBadge ok={configured.naver} />
          </div>
          <div className="space-y-4">
            {/* Client ID */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Client ID
              </label>
              <input
                type="text"
                value={keys.NAVER_CLIENT_ID}
                onChange={(e) => setKeys({ ...keys, NAVER_CLIENT_ID: e.target.value })}
                disabled={!editing}
                placeholder={editing ? '네이버 API Client ID를 입력하세요' : ''}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:bg-gray-50 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-400 font-mono"
              />
            </div>

            {/* Client Secret */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Client Secret
              </label>
              <input
                type={editing ? 'text' : 'password'}
                value={keys.NAVER_CLIENT_SECRET}
                onChange={(e) => setKeys({ ...keys, NAVER_CLIENT_SECRET: e.target.value })}
                disabled={!editing}
                placeholder={editing ? '네이버 API Client Secret을 입력하세요' : ''}
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 text-sm bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 disabled:bg-gray-50 dark:disabled:bg-gray-800 disabled:text-gray-500 dark:disabled:text-gray-400 font-mono"
              />
            </div>
          </div>
        </section>

        {/* 메시지 */}
        {message && (
          <div
            className={`p-3 rounded-lg text-sm ${
              message.type === 'success'
                ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800'
                : message.type === 'error'
                  ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800'
                  : 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-300 border border-yellow-200 dark:border-yellow-800'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* 버튼 */}
        <div className="flex gap-3">
          {editing ? (
            <>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-6 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
              >
                {saving ? '저장 중...' : '저장'}
              </button>
              <button
                onClick={handleCancel}
                disabled={saving}
                className="px-6 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors text-sm font-medium"
              >
                취소
              </button>
            </>
          ) : (
            <button
              onClick={handleEdit}
              className="px-6 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors text-sm font-medium flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
              </svg>
              수정
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
