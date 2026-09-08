import { test } from 'node:test'
import assert from 'node:assert/strict'
for (const path of ['../src/utils/numbers.js', '../../compute/frontend/src/utils/numbers.js']) {
  const { numeric, decimal, amount, percent, scaled } = await import(path)
  test(`${path}: absent values never become zero`, () => {
    for (const value of [null, undefined, '', ' ', 'invalid', NaN, Infinity]) {
      assert.equal(numeric(value), null)
      assert.equal(decimal(value), '—')
      assert.equal(amount(value), '—')
      assert.equal(percent(value), '—')
      assert.equal(scaled(value, 10000), null)
    }
    assert.equal(decimal(0), '0.00')
    assert.equal(percent(0), '0.0%')
    assert.equal(amount(0), '0')
    assert.equal(scaled('25000', 10000), 2.5)
    assert.equal(decimal(-3), '-3.00')
  })
}
