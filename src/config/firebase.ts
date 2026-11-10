/**
 * Conexão com o backend Firebase (pasta backend/). Segue a seção 7.3 da documentação do backend
 * (docs/backend/BACKEND.md).
 *
 * O app só é criado na primeira chamada de `getFirebase()`. Assim, enquanto as telas usarem os dados
 * simulados, nada do Firebase é inicializado.
 */
import { initializeApp, type FirebaseApp } from "firebase/app"
import { connectAuthEmulator, getAuth, type Auth } from "firebase/auth"
import { connectDatabaseEmulator, getDatabase, type Database } from "firebase/database"
import { connectFirestoreEmulator, getFirestore, type Firestore } from "firebase/firestore"
import { connectFunctionsEmulator, getFunctions, type Functions } from "firebase/functions"

const env = import.meta.env

/** ID real do projeto (backend/.firebaserc). Nos emuladores, os dados vivem neste projeto. */
const PROJECT_ID = env.VITE_FIREBASE_PROJECT_ID || "loirinha-1a25f"

/** Todas as functions estão nesta região. Sem ela, o SDK usa us-central1 e não acha a function. */
const FUNCTIONS_REGION = env.VITE_FUNCTIONS_REGION || "southamerica-east1"

export const firebaseConfig = {
  useEmulators: env.VITE_USE_EMULATORS === "true",
  projectId: PROJECT_ID,
  functionsRegion: FUNCTIONS_REGION,
  /** Define o namespace do RTDB (loirinha-1a25f-default-rtdb), onde ficam as regras e a telemetria. */
  databaseURL: env.VITE_FIREBASE_DATABASE_URL || `https://${PROJECT_ID}-default-rtdb.firebaseio.com`,
} as const

export type FirebaseServices = {
  app: FirebaseApp
  auth: Auth
  db: Firestore
  rtdb: Database
  functions: Functions
}

let services: FirebaseServices | null = null

/** Devolve os serviços do Firebase, criando-os (e ligando os emuladores) na primeira chamada. */
export function getFirebase(): FirebaseServices {
  if (services) return services

  const app = initializeApp({
    // No emulador a chave é irrelevante; nunca use a chave de produção em .env.local.
    apiKey: env.VITE_FIREBASE_API_KEY || "fake-api-key-local",
    authDomain: env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: firebaseConfig.projectId,
    databaseURL: firebaseConfig.databaseURL,
    appId: env.VITE_FIREBASE_APP_ID,
  })
  const auth = getAuth(app)
  const db = getFirestore(app)
  const rtdb = getDatabase(app)
  const functions = getFunctions(app, firebaseConfig.functionsRegion)

  if (firebaseConfig.useEmulators) {
    // Os connect*Emulator precisam rodar uma única vez, antes de qualquer outra operação.
    const host = env.VITE_EMULATOR_HOST || "127.0.0.1"
    connectAuthEmulator(auth, `http://${host}:${Number(env.VITE_AUTH_PORT) || 9099}`, { disableWarnings: true })
    connectFirestoreEmulator(db, host, Number(env.VITE_FIRESTORE_PORT) || 8080)
    connectDatabaseEmulator(rtdb, host, Number(env.VITE_DATABASE_PORT) || 9000)
    connectFunctionsEmulator(functions, host, Number(env.VITE_FUNCTIONS_PORT) || 5001)
  }

  services = { app, auth, db, rtdb, functions }
  return services
}
