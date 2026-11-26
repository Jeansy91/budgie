import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const goto = vi.fn();
vi.mock('$app/navigation', () => ({ goto: (...args: unknown[]) => goto(...args) }));

import { ApiError, api } from './api';

const json = (body: unknown, status = 200) =>
	new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

/** Resolves with the ApiError a request rejects with; fails the test if it succeeds. */
const failure = (p: Promise<unknown>) =>
	p.then(
		() => {
			throw new Error('expected the request to fail');
		},
		(e: ApiError) => e
	);

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
	fetchMock = vi.fn();
	vi.stubGlobal('fetch', fetchMock);
	goto.mockReset();
});
afterEach(() => vi.unstubAllGlobals());

describe('api request building', () => {
	it('sends GET with language header and same-origin credentials', async () => {
		fetchMock.mockResolvedValue(json({ ok: true }));
		await expect(api('/things')).resolves.toEqual({ ok: true });
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe('/api/things');
		expect(init).toMatchObject({ method: 'GET', credentials: 'same-origin', headers: { 'Accept-Language': 'de' } });
		expect(init.body).toBeUndefined();
	});

	it('serializes params and skips empty values', async () => {
		fetchMock.mockResolvedValue(json([]));
		await api('/tx', { params: { q: 'rewe', month: '2026-03', empty: '', no: false, nil: null, undef: undefined, n: 0, yes: true } });
		expect(fetchMock.mock.calls[0][0]).toBe('/api/tx?q=rewe&month=2026-03&n=0&yes=true');
	});

	it('adds no query string when all params are empty', async () => {
		fetchMock.mockResolvedValue(json([]));
		await api('/tx', { params: { a: '' } });
		expect(fetchMock.mock.calls[0][0]).toBe('/api/tx');
	});

	it('sends JSON bodies with content type', async () => {
		fetchMock.mockResolvedValue(json({ id: 1 }));
		await api('/tx', { method: 'POST', body: { a: 1 } });
		const init = fetchMock.mock.calls[0][1];
		expect(init.method).toBe('POST');
		expect(init.body).toBe('{"a":1}');
		expect(init.headers['Content-Type']).toBe('application/json');
	});

	it('passes FormData through without a JSON content type', async () => {
		fetchMock.mockResolvedValue(json({}));
		const form = new FormData();
		await api('/import', { method: 'POST', form });
		const init = fetchMock.mock.calls[0][1];
		expect(init.body).toBe(form);
		expect(init.headers['Content-Type']).toBeUndefined();
	});
});

describe('api responses', () => {
	it('returns undefined for 204', async () => {
		fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
		await expect(api('/x', { method: 'DELETE' })).resolves.toBeUndefined();
	});

	it('throws ApiError with string detail', async () => {
		fetchMock.mockResolvedValue(json({ detail: 'Nope' }, 400));
		const err = await failure(api('/x'));
		expect(err).toBeInstanceOf(ApiError);
		expect(err).toMatchObject({ status: 400, message: 'Nope', code: undefined });
	});

	it('exposes message and code from object detail', async () => {
		fetchMock.mockResolvedValue(json({ detail: { message: 'Locked', code: 'locked' } }, 409));
		await expect(api('/x')).rejects.toMatchObject({ status: 409, message: 'Locked', code: 'locked' });
	});

	it('joins validation messages of 422 responses', async () => {
		fetchMock.mockResolvedValue(
			json(
				{
					detail: [
						{ type: 'missing', loc: ['body', 'name'], msg: 'Field required' },
						{ type: 'other', msg: 'Custom' }
					]
				},
				422
			)
		);
		const err = await failure(api('/x'));
		expect(err.status).toBe(422);
		expect(err.message).toContain('name');
		expect(err.message).toContain('Custom');
	});

	it('falls back to a generic HTTP error for unparsable bodies', async () => {
		fetchMock.mockResolvedValue(new Response('<html>', { status: 502 }));
		const err = await failure(api('/x'));
		expect(err).toBeInstanceOf(ApiError);
		expect(err.status).toBe(502);
		expect(err.message).toContain('502');
	});

	it('redirects to /login on 401 outside /auth/', async () => {
		fetchMock.mockResolvedValue(json({ detail: 'Unauthorized' }, 401));
		await expect(api('/tx')).rejects.toBeInstanceOf(ApiError);
		expect(goto).toHaveBeenCalledWith('/login');
	});

	it('does not redirect on 401 from /auth/ endpoints', async () => {
		fetchMock.mockResolvedValue(json({ detail: 'Bad credentials' }, 401));
		await expect(api('/auth/login', { method: 'POST', body: {} })).rejects.toMatchObject({ message: 'Bad credentials' });
		expect(goto).not.toHaveBeenCalled();
	});
});
