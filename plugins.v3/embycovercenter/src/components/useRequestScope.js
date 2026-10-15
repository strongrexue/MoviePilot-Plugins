/**
 * 请求归属管理：让异步回执只作用于仍然有效的组件实例。
 *
 * 覆盖四类失效场景：插件实例切换（pluginId 变化）、路由离开、
 * KeepAlive 失活、组件卸载。过期回执一律丢弃，避免旧数据写回新页面。
 */
import {
  getCurrentInstance,
  nextTick,
  onActivated,
  onBeforeUnmount,
  onDeactivated,
  onScopeDispose,
  watch,
} from 'vue'

export function useRequestScope(owner, onInvalidate = () => {}) {
  let active = true
  let available = true
  let disposed = false
  let navigation = 0
  let epoch = 0
  const timers = new Map()

  function invalidate() {
    epoch += 1
    for (const [timer, finish] of timers) {
      clearTimeout(timer)
      finish(false)
    }
    timers.clear()
    onInvalidate()
  }

  function pause() {
    active = false
    invalidate()
  }

  function resume() {
    if (available && !disposed) active = true
  }

  function deactivate() {
    available = false
    pause()
  }

  /** 捕获当前归属；返回的函数在归属失效后恒为 false。 */
  function capture() {
    const generation = epoch
    const id = owner()
    return () => active && generation === epoch && id === owner()
  }

  function wait(ms) {
    if (!active) return Promise.resolve(false)
    return new Promise(resolve => {
      const timer = setTimeout(() => {
        timers.delete(timer)
        resolve(true)
      }, ms)
      timers.set(timer, resolve)
    })
  }

  function later(callback, ms) {
    const current = capture()
    void wait(ms).then(finished => {
      if (finished && current()) callback()
    })
  }

  watch(owner, invalidate, { flush: 'sync' })

  const instance = getCurrentInstance()
  const cleanups = []
  if (instance) {
    onBeforeUnmount(deactivate)
    onDeactivated(deactivate)
    onActivated(() => {
      available = true
      resume()
    })
    // 复用宿主 router 的公开守卫，不引入第二份 vue-router。
    const router = instance.proxy?.$router
    if (router?.beforeEach) {
      cleanups.push(
        router.beforeEach((to, from) => {
          if (to.path !== from.path) {
            navigation += 1
            pause()
          }
        }),
      )
    }
    if (router?.afterEach) {
      cleanups.push(
        router.afterEach(async () => {
          const currentNavigation = navigation
          await nextTick()
          if (currentNavigation === navigation) resume()
        }),
      )
    }
  }

  onScopeDispose(() => {
    disposed = true
    deactivate()
    for (const cleanup of cleanups) cleanup?.()
  })

  return { capture, invalidate, pause, resume, wait, later, isActive: () => active }
}
