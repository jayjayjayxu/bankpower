import { computed, ref, watch } from 'vue'
import { fetchFacilities, fetchFacility, fetchProducts, fetchProduct } from '../services/computeApi'
import { amount } from '../utils/numbers'

export function useDirectory(selectedFacilityCode, selectedProductId) {
  const facilities = ref([]), products = ref([]), facilityMetrics = ref([])
  const directoryErrors = ref({}), facilityDetail = ref(null), productDetail = ref(null)
  const directoryError = computed(() => Object.values(directoryErrors.value).filter(Boolean).join('；'))
  const fail = (key, error) => { directoryErrors.value = { ...directoryErrors.value, [key]: error?.message || '' } }
  async function allPages(fetcher) {
    let page = 0, rows = [], result
    do { result = await fetcher(page++); rows.push(...result.items) } while (page < result.totalPages)
    return rows
  }
  const label = (value, labels) => labels[value] || value || '待核验'
  const mapFacility = (f) => ({
    code: f.facilityCode, name: f.officialName, type: label(f.facilityKind, { AI_COMPUTE: '智算中心', IDC: '数据中心', DISTRIBUTED_CLUSTER: '分布式集群', SUPERCOMPUTE: '超算中心', FINANCIAL_DC: '金融数据中心' }),
    location: [f.cityName, f.districtName].filter(Boolean).join(' · '), status: label(f.lifecycleStatus, { OPERATING: '运营中', COMMISSIONING: '调试中', APPROVED_OPERATION_STATUS_UNKNOWN: '已批复·运营待核验', COMMISSIONING_PARTIAL_OPERATION: '调试及部分投运', UNDER_CONSTRUCTION_OPERATION_SCOPE_UNKNOWN: '在建·投运范围待核验' }),
    grade: label(f.dataQuality, { VERIFIED_PUBLIC: '公开核验', PARTIAL_PUBLIC: '部分公开' }), capacity: `${f.metricCount ?? 0} 项公开指标`, precision: '指标按各自范围分别保存',
    secondaryCapacity: '查看下方逐字段来源', energy: f.disclosedPue == null ? 'PUE待补充' : `公开PUE ${f.disclosedPue}（范围见指标）`,
    price: '按来源字段展示', facts: [f.operatorName && `运营方：${f.operatorName}`, f.ownerName && `所有方：${f.ownerName}`, f.lastVerifiedDate && `核验日期：${f.lastVerifiedDate}`].filter(Boolean),
    gaps: ['项目级合同、电费账单与债务资料待逐项核验'], fit: f.notes || '请结合各指标统计范围使用。', sourceUrl: f.sourceUrl,
  })
  const selectedFacility = computed(() => facilities.value.find(f => f.code === selectedFacilityCode.value) || { facts: [], gaps: [] })
  const selectedProduct = computed(() => {
    const row = products.value.find(p => p.id === selectedProductId.value) || {}
    const prices = productDetail.value?.prices || []
    const list = prices.find(p => p.priceScope === 'LIST_REFERENCE')
    // Never compare different units/currencies/billing periods as a price conflict.
    const detail = prices.find(p => p.priceScope === 'DETAIL_CONFIG' && (!list ||
      (p.priceUnit === list.priceUnit && p.currency === list.currency && p.billingCycle === list.billingCycle)))
    return { ...row, listPrice: list?.priceValue ?? null, detailPrice: detail?.priceValue ?? null,
      unit: list?.priceUnit || detail?.priceUnit || '单位待核验',
      conflict: !!(list && detail && Number(list.priceValue) !== Number(detail.priceValue)),
      capturedAt: list?.capturedAt || detail?.capturedAt, sourceUrl: list?.sourceApiUrl || detail?.sourceApiUrl }
  })
  let facilityRequest = 0, productRequest = 0
  async function loadFacility() {
    const version = ++facilityRequest
    facilityMetrics.value = []; facilityDetail.value = null; fail('facility', null)
    try {
      const result = await fetchFacility(selectedFacilityCode.value)
      if (version !== facilityRequest) return
      facilityDetail.value = result.facility; facilityMetrics.value = result.metrics
    } catch (e) { if (version === facilityRequest) fail('facility', e) }
  }
  async function loadProduct() {
    const version = ++productRequest
    productDetail.value = null; fail('product', null)
    const item = products.value.find(p => p.id === selectedProductId.value)
    if (!item) return
    try { const result = await fetchProduct(item.listingId); if (version === productRequest) productDetail.value = result }
    catch (e) { if (version === productRequest) fail('product', e) }
  }
  async function initializeDirectory() {
    await Promise.allSettled([
      (async () => {
        fail('facilities', null)
        try { facilities.value = (await allPages(fetchFacilities)).map(mapFacility); await loadFacility() }
        catch (e) { fail('facilities', e) }
      })(),
      (async () => {
        fail('products', null)
        try {
          products.value = (await allPages(fetchProducts)).map(p => ({
            id: String(p.listingId), listingId: p.listingId, name: p.productName, type: p.resourceType,
            region: p.platformRegionLabel || p.physicalRegionText, model: `${amount(p.acceleratorCount)} × ${p.acceleratorModel || '型号待核验'}`,
            source: p.platformName,
          }))
          if (!products.value.some(p => p.id === selectedProductId.value)) selectedProductId.value = products.value[0]?.id || ''
          await loadProduct()
        } catch (e) { fail('products', e) }
      })(),
    ])
  }
  watch(selectedFacilityCode, loadFacility)
  watch(selectedProductId, loadProduct)
  return { facilities, products, selectedFacility, selectedProduct, facilityMetrics, directoryError, initializeDirectory }
}
