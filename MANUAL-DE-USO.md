# Manual de uso · Gastos Bimonetarios

Guía para usar el programa sin conocimientos técnicos. Explica qué hace, cómo se
abre, qué significa cada pantalla y cómo resolver los problemas habituales.

> Este documento es para el día a día. Para el detalle técnico (instalación,
> arquitectura y pruebas) consulta `README.md`.

---

## 1. Qué es (y qué no es)

**Es** una aplicación local para llevar tus gastos en **bolívares y dólares a la
vez**. Cada compra guarda las dos cifras usando la tasa del día en que la
registraste, y a partir de ahí puedes ver totales, gráficos, análisis y reportes.

**No es** una aplicación en la nube ni un servicio web:

- Se ejecuta **en tu computadora**. Los datos no salen de ella (la única consulta
  a internet es opcional: sincronizar la tasa del BCV).
- No hay usuarios, contraseñas ni sincronización entre equipos.
- No se cierra al cerrar el navegador: se cierra al cerrar la **ventana negra**
  (la consola) que la arranca.

---

## 2. Cómo abrirla y cerrarla

### Abrir

1. Entra a la carpeta del programa.
2. Haz **doble clic en `iniciar.bat`**.
3. Se abre una ventana negra (el servidor) y, a los pocos segundos, tu navegador
   en `http://127.0.0.1:8080`.

Si el navegador no se abre solo, ábrelo tú y entra a esa dirección.

### Cerrar

- Cierra la **ventana negra** (o pulsa `Ctrl+C` dentro de ella).
- Cerrar solo la pestaña del navegador **no** detiene el programa: sigue
  funcionando en segundo plano hasta que cierres la consola.

### Cosas importantes

- **No abras `iniciar.bat` dos veces.** El segundo intento fallará porque el
  puerto 8080 ya está ocupado. Si te pasa, cierra la ventana negra anterior.
- Mientras la ventana negra esté abierta, puedes cerrar y abrir la pestaña del
  navegador tantas veces como quieras: los datos siguen ahí.
- El servidor solo acepta conexiones de tu propia máquina (`127.0.0.1`). No está
  expuesto a internet.

---

## 3. La pantalla de un vistazo

Arriba hay una **cabecera** fija y debajo **nueve pestañas**.

### Cabecera

| Elemento | Qué es |
|---|---|
| **Gastos Bimonetarios** + etiqueta de tasa | El nombre y la **tasa activa**. Si dice «Sin tasa registrada», no podrás guardar compras. |
| **Entorno** (`Personal` / `Profesional`) | Dos libretas **separadas**. Lo que registras en una no aparece en la otra. |
| Caja numérica junto al entorno | El **año fiscal** (por ejemplo `2026`). Filtra todo lo que ves. |
| **Moneda** (`Dólares (USD)` / `Bolívares (VES)`) | Solo cambia **cómo se muestran** los importes. Los datos guardan siempre ambas monedas. |
| Caja numérica junto a la moneda | **Decimales** que se muestran (0 a 6). Por defecto 3. |
| **Tema** (`Oscuro` / `Claro`) | Cambia los colores. Al cambiarlo, la página se recarga. |

> La etiqueta de la tasa se pone **ámbar** cuando has fijado una tasa manual
> (sigue fijada hasta que la sueltes), y **roja** cuando no hay ninguna tasa.

### Las nueve pestañas y para qué sirven

| Pestaña | Para qué |
|---|---|
| **Dashboard** | Resumen del año: total, proyección del mes, ritmo, compromisos, gráficos y últimos movimientos. |
| **Registrar** | Dar de alta una compra. |
| **Catálogo** | Fichas de productos (SKU): nombre, marca, unidad, comercio habitual. |
| **Categorías** | Bolsas de gasto (Alimentación, Salud…) y qué campos pide cada una. |
| **Análisis** | Precios, variantes, pivotes, frecuencia, proyecciones y extras. |
| **Reportes** | Exportar a Excel/CSV, respaldo JSON, acta y cierre del ejercicio. |
| **Tasas** | Tasa activa, tasa manual, sincronización con el BCV e historial. |
| **OCR** | Importar tickets desde una foto o texto pegado. |
| **Configuración** | Preferencias, datos de demostración y borrado total. |

**Orden recomendado la primera vez:** Tasas → (Categorías) → (Catálogo) →
Registrar. El catálogo y las categorías ya vienen con datos de ejemplo, así que
en la práctica puedes empezar por **Tasas** y luego **Registrar**.

---

## 4. Conceptos básicos

### Bimonetario

Cada compra guarda **cuánto pagaste en bolívares** y **su equivalente en
dólares**, calculado con la tasa de ese día. Si mañana la tasa cambia, la compra
de ayer **no se recalcula**: queda congelada. Así los totales en dólares no se
mueven cuando el bolívar se devalúa.

### Tasa

Es el precio del dólar en bolívares (`Bs/USD`). Se usa para:

- convertir lo que pagas en Bs a USD (y al revés), y
- los totales y gráficos.

La **tasa activa** es la de **fecha más reciente** del historial. Si guardas una
tasa manual, queda **fijada** (también si recargas la página o cierras y vuelves a
abrir la aplicación) aunque exista una del BCV más nueva. Al sincronizar con el
BCV o pulsar «Volver a la automática», se suelta.

### Año fiscal

El año que estás viendo (`2026` por defecto). Dashboard, Reportes y Análisis
trabajan **solo** con las compras de ese año. Cambia el número de la cabecera
para ver otro año.

### Entorno

`Personal` y `Profesional` son dos espacios independientes. El botón «Cargar
demo» carga los datos de ejemplo **en el entorno activo**. Cambiar de entorno
cambia todo lo que ves.

### Categoría y SKU

- **Categoría**: el grupo del gasto («Alimentación y Abastecimiento», «Salud y
  Farmacia»…). Define además **qué campos pide** el formulario.
- **SKU**: la ficha del producto concreto («Harina de Maíz Precocida 1kg»). El
  SKU recuerda marca, unidad y comercio habitual, y se reutiliza la próxima vez.

Al registrar, si el producto no existe, **se crea solo** el SKU con los datos que
hayas escrito. No hace falta crearlo antes en el Catálogo.

### Modalidad de IVA

| Modalidad | Qué significa | Ejemplo con 116 Bs |
|---|---|---|
| **Exento** | No lleva IVA. | Base 116 · IVA 0 · Total 116 |
| **IVA incluido** | El monto que escribes **ya incluye** el IVA. | Base 100 · IVA 16 · Total 116 |
| **IVA + 16%** | El IVA **se suma** al monto que escribes. | Base 116 · IVA 18,56 · Total 134,56 |

Elige la que corresponda al ticket. La vista previa te muestra Base, IVA, Total y
el equivalente en dólares antes de guardar.

### Naturaleza

- **Recurrente**: gasto que se repite (alquiler, internet, teléfono).
- **Extraordinario**: gasto puntual (una reparación, un regalo).

El Dashboard usa esta marca para los «compromisos recurrentes» y el reparto
«fijo vs. variable».

---

## 5. Primeros cinco minutos (con datos de ejemplo)

1. Abre la app (`iniciar.bat`).
2. Ve a **Configuración**.
3. Pulsa **Cargar demo**. Se cargan 23 compras de ejemplo, 8 SKU y 9 tasas en el
   entorno activo. **No borra** lo que ya tengas.
4. Vuelve a **Dashboard**: verás el total del año, la proyección del mes, el
   ritmo, los compromisos, la evolución mensual, el reparto por categoría y los
   últimos movimientos.
5. Entra a **Análisis** y cambia el período (Mes, Trimestre, Año…) con las
   flechas.
6. Entra a **Reportes** y pulsa **Excel (6 hojas)** para ver un reporte completo.

Cuando quieras empezar de cero: **Configuración → Borrar todos los datos…**.
Después puedes volver a cargar la demo o registrar tus compras reales.

---

## 6. Registrar una compra (paso a paso)

Entra a **Registrar**. Arriba verás la tasa que se usará.

1. **Fecha**: viene con la de hoy. Cámbiala si la compra es de otro día.
2. **Categoría**: elige la bolsa del gasto. Al cambiarla, el formulario **muestra
   u oculta campos** según lo configurado en esa categoría.
3. **Producto**: escribe el nombre. Si ya existe, se reutiliza; si no, se crea el
   SKU. Sé consistente con los nombres («Harina 1kg», no «harina» y «Harina»).
4. **Cantidad / Unidad / Marca / Subcategoría / Comercio**: solo si tu categoría
   los pide. Sirven para comparar precios por unidad y saber dónde compraste.
5. **Forma de pago**: efectivo, Pago Móvil, punto de venta, Zelle…
6. **Plataforma origen**: dónde se hizo el pago (Binance P2P, Zinli, bancos…).
   Es opcional; sirve para el análisis de plataformas.
7. **Naturaleza**: `Recurrente` o `Extraordinario`.
8. **Modalidad IVA**: `Exento`, `IVA incluido` o `IVA + 16%`.
9. **Monto Bs** (obligatorio): el total pagado en bolívares.
   - Si solo tienes el monto en dólares, escríbelo en **Monto USD (opcional)** y
     el programa calcula los bolívares con la tasa activa.
10. Revisa la vista previa: **Base**, **IVA**, **Total** y **≈ $**.
11. Si el precio se aleja mucho de lo que sueles pagar por ese producto, aparece
    un **aviso de precio** con la media y el mínimo histórico.
12. Pulsa **Guardar compra**. La compra aparece abajo, en **Movimientos
    recientes**, y todos los paneles se actualizan.

> Si la categoría define **campos personalizados** (por ejemplo «Presentación /
> Empaque», «Nro. Contrato / Medidor» o «Kilometraje»), aparecen al final del
> formulario. Son propios de esa categoría y se guardan con la compra. Se
> administran en **Categorías → Editar**.

**Limpiar** vacía el formulario para la siguiente compra.

> Si no hay tasa activa, el programa no deja guardar. Ve a **Tasas** primero.

---

## 7. Corregir o borrar una compra

En **Registrar**, debajo de «Movimientos recientes», está la tarjeta **Corregir un
movimiento**:

1. Abre la lista **Movimiento** (puedes escribir para filtrar).
2. Elige la compra (verás `#número · fecha · producto · total`).
3. Pulsa **Editar** para cambiar sus datos o **Borrar** para eliminarla.

La lista muestra los **50 movimientos más recientes**. Los más antiguos se pueden
consultar en **Reportes → CSV · movimientos**.

### Editar

Se abre una ventana con los datos de la compra: fecha, producto, monto en Bs,
monto en USD, modalidad de IVA, tasa aplicada, y —si la categoría los pide—
cantidad, unidad, marca, comercio, plataforma de origen y campos personalizados.
También las notas.

- Al cambiar el **Monto Bs**, el **Monto USD** se recalcula con la tasa del
  formulario; al cambiar el **Monto USD**, se recalcula el **Monto Bs**. Si
  cambias la **tasa**, se recalcula el monto en Bs a partir del USD.
- La vista previa muestra **Base**, **IVA** y **Total** antes de guardar.
- **Guardar cambios** actualiza la compra y todos los paneles.
- La **categoría** no se cambia desde aquí. Si te equivocaste de categoría,
  borra la compra y regístrala de nuevo.
- El **SKU** tampoco se modifica: la compra guarda el nombre que escribas, pero la
  ficha del catálogo queda como estaba.

> El editor parte de la **tasa guardada en esa compra**, no de la tasa activa. Si
> cambias la tasa, el cambio afecta **solo a esa compra**; las demás conservan la
> suya.

### Borrar

**Borrar** pide confirmación y elimina la compra. **No hay papelera**: si fue un
error, restaura un respaldo (sección 15) o vuelve a registrarla.

> Borrar una compra **no** borra el SKU ni la categoría. Y borrar un SKU o una
> categoría **no** borra las compras que los usaban: el histórico se conserva.

---

## 8. Tasas

Es la primera pestaña que conviene mirar. Arriba se muestra la **tasa activa**
con su fecha y su fuente.

### Guardar una tasa manual

1. Escribe la **Fecha** (viene con hoy).
2. Escribe la **Tasa Bs/USD**.
3. Pulsa **Guardar tasa**.

La tasa queda **fijada**: se usa en la vista previa, en las compras nuevas y en
los totales, aunque en el historial haya una del BCV con fecha más reciente.
Verás la etiqueta «Tasa de sesión fijada a mano» y el botón **Volver a la
automática** para soltarla.

La elección se **recuerda al recargar la página y al cerrar y abrir la
aplicación** (se guarda en la tabla `config` de la base de datos). Sigue fijada
hasta que pulses **Volver a la automática**, sincronices con el BCV o borres todos
los datos.

### Sincronizar con el BCV

Pulsa **Sincronizar con el BCV**. El programa consulta varios servicios públicos
y guarda la tasa del día. Si todos fallan (sin internet o servicios caídos), te
avisa: en ese caso, usa la tasa manual.

Sincronizar **suelta** la tasa manual y vuelve a la automática.

### Historial

Lista todas las tasas guardadas, de la más reciente a la más antigua. Cada una se
puede **Borrar**. La tasa que se aplica a cada compra ya registrada no cambia.

---

## 9. Catálogo (SKU) y Categorías

### Catálogo

- **Buscar** por nombre, marca o SKU.
- **Nuevo SKU**: nombre, categoría, marca, unidad y comercio habitual.
- **Editar** / **Borrar** en cada fila.

Un SKU es una ficha reutilizable: al registrar, si escribes el mismo nombre, se
usan sus datos. **Borrar un SKU no borra las compras** ya registradas.

### Categorías

- Cada fila muestra el color, el número de movimientos, los campos habilitados y
  cuántos campos personalizados tiene.
- **Nueva categoría**: nombre, color, casillas de campos estándar y **campos
  personalizados**.
- Las casillas **Comercio**, **Subcategoría**, **Cantidad**, **Marca** y **Unidad**
  controlan qué campos aparecen en **Registrar** para esa categoría. Si
  desmarcas «Cantidad», el formulario no la pedirá.
- **Campos personalizados**: además de los estándar, cada categoría puede definir
  los suyos (por ejemplo «Presentación / Empaque» o «Kilometraje»). Cada campo
  lleva nombre, tipo (**Texto**, **Número**, **Lista** o **Sí/No**), si es
  obligatorio y —solo para las listas— las opciones separadas por coma. Aparecen
  al final del formulario de **Registrar** y en el editor de compras.
- **Editar** / **Borrar**. Borrar una categoría no borra las compras; solo deja de
  estar disponible para clasificar.

> Las siete categorías iniciales ya vienen creadas y algunas traen campos
> personalizados de ejemplo («Presentación / Empaque», «Kilometraje», «RIF
> Proveedor»…). Puedes renombrarlas, recolorearlas, cambiar sus campos o añadir las
> tuyas.

---

## 10. Dashboard: qué significa cada número

| Tarjeta | Qué muestra |
|---|---|
| **Ejercicio 2026** | Total gastado en el año (en la moneda elegida) y número de movimientos. |
| **Proyección del mes** | Estimación de lo que gastarás este mes si sigues al ritmo actual. La barra indica el avance del mes y debajo dice «Corte día X de Y». |
| **Ritmo vs mes previo** | Comparación con el mismo punto del mes anterior. Si no hay datos previos, muestra «Sin base previa». |
| **Compromisos recurrentes** | Suma de los gastos recurrentes pendientes del mes y cuántos se detectaron. |
| **Evolución mensual** | Barras de gasto por mes del año. |
| **Reparto por categoría** | Dona con el peso de cada categoría. |
| **Fijo vs. variable** | Proporción de gastos recurrentes frente a extraordinarios. |
| **Últimos movimientos** | Las 12 compras más recientes del año, con cantidad, total e IVA. |

Todo el Dashboard respeta el **año fiscal** y el **entorno** de la cabecera.

---

## 11. Análisis

Primero elige el **período**:

- Tipo: Semana, Mes, Bimestre, Trimestre, Cuatrimestre, Semestre, Año o
  Personalizado.
- Muévete con las flechas `‹` `›`. El rango exacto se muestra debajo.

Luego, las siete sub-pestañas:

| Sub-pestaña | Qué responde |
|---|---|
| **Precios** | Histórico de precios de un producto, mayores subidas y productos más estables. |
| **Variantes** | Compara presentaciones (unidad, marca, comercio…): cuál sale más económica por unidad. |
| **Pivote** | Cruces por comercio, método de pago, etc., con filtro por producto y opción «solo compras del mismo día». |
| **Frecuencia** | Cada cuánto compras cada producto y cuánto gastas por período. |
| **Proyecciones** | Proyección de la tasa de cambio y del precio de un producto. |
| **Categorías** | Impacto por categoría y reparto por método de pago. |
| **Extras** | Semáforo de presupuesto por categoría, Pareto 80/20, dispersión diaria, árbol categoría → subcategoría → producto y tabla de productos. |

Las cifras de Análisis usan el **período elegido**, no todo el año.

---

## 12. Reportes

### Exportar

| Botón | Qué genera |
|---|---|
| **Excel (6 hojas)** | Un `.xlsx` con: 1. Resumen · 2. Libro Mayor · 3. Catálogo SKUs · 4. Análisis Precios · 5. Categorías y Pagos · 6. Tasas y Proyecciones. |
| **CSV · movimientos** | Todas las compras del año con sus campos. |
| **CSV · catálogo** | Los SKU. |
| **CSV · tasas** | El historial de tasas. |
| **Respaldo JSON completo** | Todo: compras de todos los entornos, catálogo, categorías, tasas, cierres y preferencias. **Es la copia de seguridad recomendada.** |

El navegador descarga los archivos a tu carpeta de descargas.

### Importar un respaldo

**Importar respaldo JSON** lee un archivo generado por esta aplicación y **añade**
lo que falte. No borra nada. Las compras duplicadas (misma firma: entorno, fecha,
producto e importe) se descartan, así que puedes importar el mismo respaldo dos
veces sin miedo.

### Acta y cierre del ejercicio

Abajo, **Acta de cierre del ejercicio** resume el año: movimientos, total, IVA,
devaluación e inflación media.

- **Descargar acta (HTML)**: un documento para guardar o imprimir.
- **Cerrar y archivar ejercicio**: guarda un **snapshot** del año en el historial
  de cierres. La casilla «Limpiar transacciones de 2026 tras archivar el Acta»
  permite además **borrar las compras de ese año** (el catálogo, las categorías y
  las tasas se conservan).

> Cerrar el ejercicio es la operación habitual a fin de año. **No** cierres un
> año a medias: si borras las compras, ya no podrás consultarlas en el Dashboard.

---

## 13. OCR de tickets

Entra a **OCR**.

1. **Sube una imagen** (foto o captura del ticket). El reconocimiento se hace en
   tu equipo con RapidOCR, sin internet.
2. O **pega el texto** del ticket en el cuadro y pulsa **Añadir texto pegado**.
3. Revisa el **Lote a importar**: fecha, categoría, modalidad de IVA y comercio
   para todo el lote; y por cada línea, nombre, cantidad y total en Bs. Puedes
   borrar líneas con el icono de papelera.
4. Pulsa **Importar N compras**.

Cada línea crea una compra con la **tasa activa**, la subcategoría
«Importado OCR» y la fuente `OCR·lote`. Después se sincronizan categoría,
unidad, marca y comercio con el SKU correspondiente.

> Necesitas una **tasa activa** y al menos una categoría. Si el chip dice «OCR no
> instalado», instala el motor con `pip install rapidocr-onnxruntime`; mientras
> tanto puedes pegar el texto a mano.

---

## 14. Configuración

- **Preferencias**: los mismos controles de la cabecera (entorno, moneda,
  decimales, año fiscal y tema).
- **Datos de demostración**: carga 23 compras, 8 SKU y 9 tasas en el entorno
  activo. No borra lo existente.
- **Almacenamiento**: cuántos registros hay en cada tabla, el tamaño y la ruta
  exacta de la base de datos.
- **Borrar todos los datos…**: vacía las **cinco tablas de datos** (también las de
  otros entornos). Vuelve a crear las **siete categorías** iniciales para que la
  app siga siendo usable, pero **no** recupera compras, SKU, tasas ni cierres. Las
  preferencias de la cabecera se conservan; la tasa manual se suelta. **No se
  puede deshacer.**

---

## 15. Tus datos: la base de datos explicada

Esta es la sección más técnica del manual, pero está escrita para que se entienda
sin ser programador. Si solo quieres lo práctico: **haz un respaldo JSON cada
semana y antes de cualquier cambio grande** (15.6).

### 15.1 Dónde está todo

Todo vive en **un solo archivo**:

```
data\gastos-bimonetarios.sqlite3
```

Ese archivo contiene las compras, el catálogo, las categorías, las tasas, los
cierres y las preferencias. No hay una carpeta por año ni un archivo por entorno:
si copias el archivo, copias todo; si se pierde, se pierde todo (salvo que tengas
un respaldo).

La ruta exacta también aparece en **Configuración → Almacenamiento**.

### 15.2 Qué es una base de datos (en palabras simples)

Es un **archivo** que guarda información en **tablas**, como una hoja de Excel con
varias pestañas. La diferencia es que la base de datos está pensada para que el
programa lea y escriba **filas** sueltas sin cargar todo, y para que dos
operaciones no se pisen.

Una tabla es una planilla; una **fila** es un renglón (una compra); una
**columna** es un dato de ese renglón (fecha, producto, monto…). Cada fila tiene un
**ID**: un código único, como el número de una factura. El ID no cambia aunque
cambies el nombre del producto.

Tres ideas que explican casi todo lo demás:

1. **Cada acción escribe al instante.** No hay botón «guardar archivo»: al pulsar
   «Guardar compra», la fila ya está en el archivo.
2. **Las cosas se enlazan por ID, no por nombre.** Una compra apunta a la
   categoría y al SKU por su ID. Por eso puedes renombrar una categoría sin
   romper el histórico.
3. **El histórico es una foto.** Cada compra guarda su propia tasa, su base, su
   IVA y sus dos importes. Cambiar una tasa del historial **no** recalcula las
   compras de ayer.

### 15.3 Las seis tablas

| Tabla | Qué guarda | Cómo se reconoce |
|---|---|---|
| `transactions` | Cada compra: fecha, producto, Bs, USD, IVA, tasa aplicada, notas… | `id` numérico (#1, #2…) |
| `products` | Catálogo/SKU: nombre, marca, unidad, comercio habitual | `id` que empieza por `PROD-` |
| `categories` | Categorías: nombre, color, campos que pide y campos personalizados | `id` que empieza por `cat_` o `CAT-` |
| `rates` | Histórico de tasas Bs/USD | la **fecha** es la clave |
| `closures` | Cierres anuales (la foto de un año) | `id` que empieza por `closure_` |
| `config` | Preferencias: tema, entorno, moneda, decimales, año y tasa manual | pares `key` / `value` |

Cómo se relacionan:

```
categories ──┐
             ├──< transactions >── products
rates ───────┘        │
                      └── config (preferencias, tasa manual)
closures (foto de las compras de un año)
```

- `transactions.categoryId` apunta a `categories.id`.
- `transactions.productId` apunta a `products.id`.
- `transactions.rate` guarda la tasa que se usó (y `rateDate` / `rateSource`, de
  dónde salió). Por eso borrar una tasa del historial no cambia lo ya comprado.
- `transactions.year` se deriva de la fecha y sirve para filtrar rápido. Si
  editas la fecha, el año se actualiza solo.
- `workspace` (`personal` / `profesional`) separa las libretas en todas las tablas
  menos en `rates` y `config`, que son globales.
- `customFields` (en la categoría) y `customValues` (en la compra) se guardan como
  texto JSON: son los campos personalizados de esa categoría.

**Borrar no arrastra el histórico.** Si borras una categoría o un SKU, las compras
siguen ahí: conservan el ID y el nombre que tenían. Por eso el Dashboard no pierde
dinero al limpiar el catálogo. (Al **renombrar** un SKU sí se actualiza el nombre
en sus compras.)

### 15.4 Cómo se escribe (y por qué no hay botón «Guardar»)

No hay un documento abierto que puedas dejar sin guardar. Cada operación (guardar
una compra, editarla, borrarla, cambiar una preferencia) es una escritura
inmediata en el archivo.

- Puedes cerrar el navegador cuando quieras: lo guardado ya está guardado.
- **No hay papelera ni deshacer.** Un borrado es definitivo; la única vuelta atrás
  es un respaldo.
- El servidor (la ventana negra) es quien escribe. Si cierras la ventana negra, la
  página deja de funcionar, pero los datos quedan.

### 15.5 Los archivos `-wal` y `-shm`

Mientras la aplicación está abierta pueden aparecer dos archivos al lado de la
base:

```
gastos-bimonetarios.sqlite3-wal
gastos-bimonetarios.sqlite3-shm
```

Son **normales**. SQLite escribe primero los cambios en el `-wal` (una bitácora) y
usa el `-shm` como coordinador. Al cerrar la aplicación correctamente, los cambios
se integran al archivo principal y esos dos archivos desaparecen.

- **No los borres ni los muevas con la app abierta.**
- Si la app se cerró de golpe, al volver a abrirla SQLite recupera lo pendiente del
  `-wal` automáticamente.
- Para copiar la base a mano, **cierra la app primero**. Si no puedes, copia los
  tres archivos juntos; copiar solo el principal puede dejar fuera los últimos
  cambios.

### 15.6 Copias de seguridad: tres formas (y cuál usar)

| Forma | Qué contiene | Para qué sirve | Cómo se restaura |
|---|---|---|---|
| **Respaldo JSON** | Todas las filas de las 5 tablas de datos (los dos entornos) y las preferencias, en texto | Copia del día a día, mover de PC, guardar versiones | **Reportes → Importar respaldo JSON** |
| **Copia del `.sqlite3`** | El archivo exacto, con estructura e índices | Clon exacto y vuelta atrás total | Cerrar la app y reemplazar el archivo |
| **Excel / CSV** | Un reporte legible | Leer, compartir, contabilidad | **No** es un respaldo: no restaura IDs ni campos personalizados |

**Recomendación:** un **Respaldo JSON** cada semana y siempre antes de borrar
datos, cerrar un ejercicio o actualizar el programa. Guarda 2 o 3 copias rotadas
**fuera** de la carpeta del programa (otra carpeta, un pendrive, tu nube privada).

#### Restaurar un respaldo JSON

1. Ve a **Reportes → Importar respaldo JSON** y elige el archivo.
2. La importación **añade** lo que falta. No borra lo que ya tienes.
3. Las compras duplicadas (misma firma: entorno, fecha, producto e importe) se
   descartan, así que puedes importar el mismo archivo dos veces sin miedo.

> Para una restauración **exacta** (volver a como estaba el día del respaldo):
> primero **Configuración → Borrar todos los datos…** y después importa el JSON.
> Si no borras, lo que hayas cambiado después del respaldo se conserva.

#### Restaurar una copia del archivo

1. Cierra la aplicación (la ventana negra) y espera a que desaparezcan `-wal` y
   `-shm`.
2. Renombra la base actual a `gastos-bimonetarios.sqlite3.old` (no la borres).
3. Copia tu respaldo con el nombre exacto `gastos-bimonetarios.sqlite3` en la
   carpeta `data`.
4. Abre la app. Comprueba el Dashboard y las cifras antes de borrar la `.old`.

> No mezcles métodos: si restauras el archivo, no hace falta importar el JSON, y
> al revés.

### 15.7 Mover la aplicación a otra computadora

La base no guarda rutas absolutas, así que el archivo funciona en cualquier
carpeta. Dos caminos:

- **Solo los datos:** lleva el JSON al otro equipo, instala allí la aplicación e
  impórtalo. Es lo más simple y seguro.
- **Todo el proyecto:** con la app cerrada, copia la carpeta del programa
  **incluyendo `data\gastos-bimonetarios.sqlite3`**. No copies `.venv` si el otro
  equipo tiene otra versión de Python: créalo de nuevo e instala
  `requirements.txt` (ver `README.md`).

### 15.8 Varias pestañas y dos programas a la vez

- **Varias pestañas del navegador: sí.** Comparten el archivo. Cada pestaña tiene
  su propia vista (año, entorno, moneda, decimales, tema y tasa manual en
  memoria). Un cambio hecho en una pestaña puede tardar en verse en la otra hasta
  que cambies de panel o recargues.
- **Dos ventanas negras (dos servidores) sobre el mismo archivo: no.** El segundo
  intento falla por el puerto ocupado. Si fuerzas otro puerto, SQLite permite un
  solo escritor y puedes ver el error `database is locked`.
- **DB Browser for SQLite u otro programa mirando la base:** solo lectura es
  seguro. Si vas a editar a mano, cierra la app primero; si no, los cambios pueden
  pisarse o bloquearse.

### 15.9 Privacidad y seguridad

- La base **no está cifrada**. Cualquiera que tenga el archivo (o acceso a tu
  sesión de Windows) puede leerlo.
- La aplicación **no envía datos a ningún lado**: no hay nube, cuenta ni
  telemetría. La única conexión es la sincronización opcional con el BCV.
- Los respaldos también son legibles (el JSON es texto). Guárdalos en un lugar
  privado; si usas un servicio en la nube, ten en cuenta que el archivo no va
  cifrado.
- El servidor escucha solo en `127.0.0.1`, así que no queda expuesto a internet.
  No lo cambies sin saber lo que haces.

### 15.10 Mirar los datos sin romper nada

- **Configuración → Almacenamiento** muestra cuántas filas hay en cada tabla, el
  tamaño y la ruta del archivo.
- Para curiosear, instala **DB Browser for SQLite** (gratis) y abre una **copia**
  del archivo. Es la forma cómoda de ver las tablas como planillas. No edites a
  mano si no estás seguro: un ID o un JSON mal escrito puede dejar una compra
  invisible.
- Excel **no** puede abrir `.sqlite3`. Para llevar los datos a Excel usa
  **Reportes → Excel** o los CSV.

### 15.11 Si algo sale mal

| Síntoma | Qué pasó | Qué hacer |
|---|---|---|
| La app arranca **vacía** (solo categorías) | Se movió la carpeta, se abrió otra base o se borró `data` | Cierra, revisa la ruta en Configuración o restaura tu respaldo. No vuelvas a escribir datos a ciegas. |
| `database is locked` | Otra ventana negra o DB Browser está usando el archivo | Cierra la otra instancia, espera unos segundos y reintenta. |
| Quedan `-wal` y `-shm` | La app se cerró de golpe | Abre la app una vez y ciérrala normalmente; no los borres a mano. |
| «File is not a database» o el archivo no abre | Archivo corrupto o reemplazado por otro tipo de archivo | Restaura la última copia (archivo o JSON). No uses «reparadores» a ciegas. |
| Borraste algo por error | No hay papelera | Restaura el respaldo más reciente; el JSON vuelve a añadir lo que falte. |
| Quieres actualizar el programa | Puede cambiar la estructura de las tablas | **Respalda primero.** Las tablas se crean si faltan, pero todavía no hay migraciones automáticas: sigue las notas de la versión nueva. |

### 15.12 Tamaño y rendimiento

- Con los datos de ejemplo (23 compras), la base pesa unos **120 KB**.
- Miles de compras ocupan unos pocos MB y se consultan sin problema: el Dashboard
  filtra por entorno y año usando índices.
- Borrar filas **no encoge** el archivo: SQLite reutiliza el espacio. Es normal.
  Compactarlo (`VACUUM`) es una operación técnica y no hace falta para el uso
  normal.
- Si algún día la app va lenta, usa los filtros de año y período antes de pensar
  en la base.

**Antes de borrar todos los datos o cerrar un ejercicio, haz un respaldo.**

---

## 16. Problemas frecuentes

| Síntoma | Causa probable | Solución |
|---|---|---|
| El navegador no abre o la página queda en blanco | El servidor aún no arrancó o el puerto está ocupado | Espera a ver `NiceGUI ready to go` en la ventana negra. Si no aparece, revisa que no haya otra instancia abierta. |
| «El puerto 8080 ya está en uso» | Abriste `iniciar.bat` dos veces | Cierra la ventana negra anterior y vuelve a abrir. |
| «Sin tasa registrada» y no deja guardar | No hay ninguna tasa | Ve a **Tasas** y guarda una manual o sincroniza con el BCV. |
| «No hay categorías en este entorno» | Se borraron las categorías | Abre **Configuración → Borrar todos los datos…** (vuelve a sembrarlas) o recarga la página. |
| La sincronización con el BCV falla | Sin internet o servicios caídos | Guarda la tasa a mano. |
| Los importes no coinciden con lo que esperaba | Estás viendo otra moneda, otro año u otro entorno | Revisa la cabecera: entorno, año, moneda y decimales. |
| Borré algo por error | No hay papelera | Restaura el último respaldo JSON o la copia del `.sqlite3`. |
| La app arranca **vacía** (solo categorías) | Se movió la carpeta o se abrió otra base | Revisa **Configuración → Almacenamiento** y restaura tu respaldo (15.11). |
| «database is locked» | Dos programas usan el mismo archivo | Cierra la otra ventana negra o DB Browser y reintenta. |
| Aparecen archivos `-wal` y `-shm` | La app está abierta | Es normal; no los borres (15.5). |
| La app va lenta con muchos datos | SQLite y gráficos en el navegador | Es normal con miles de filas; usa los filtros de año y período. |

### Para usuarios técnicos

- Arranque manual: `.venv\Scripts\python.exe main.py --port 8080`.
- Otro puerto: `main.py --port 8081`.
- Base de datos alternativa: `main.py --db ruta\al\archivo.sqlite3`.
- Pruebas: `.venv\Scripts\python.exe -m pytest`.
- Estado del proyecto y arquitectura: `README.md`.

---

## 17. Limitaciones conocidas

- El editor de compras no permite cambiar la **categoría** ni la **ficha del SKU**:
  si te equivocaste en eso, borra la compra y vuelve a registrarla (sección 7).
- **Un solo usuario**, sin contraseña. No expongas el puerto a internet.
- El borrado total y el cierre con limpieza son **irreversibles**.
- El **redondeo** se hace con los decimales configurados; los totales pueden
  diferir en céntimos de una suma hecha a mano.
- Al importar un respaldo, los valores `NaN`/infinitos se guardan como vacío en
  la base de datos.
- El **OCR** de tickets usa RapidOCR (local). La calidad depende de la foto: el
  texto reconocido puede variar, pero el lote se revisa y se corrige antes de
  importar.
- Los **gráficos** usan ECharts y el **Excel** usa openpyxl; la información es la
  misma, pero el dibujo y los bytes del archivo pueden variar.

---

## 18. Glosario

| Término | Significado |
|---|---|
| **Bimonetario** | Que maneja dos monedas a la vez (bolívares y dólares). |
| **Tasa** | Precio del dólar en bolívares (`Bs/USD`). |
| **Tasa activa** | La que se usa ahora mismo para convertir y calcular. |
| **Ejercicio / año fiscal** | El año que estás consultando. |
| **Entorno** | Espacio de datos independiente: Personal o Profesional. |
| **SKU** | Ficha de un producto concreto (nombre, marca, unidad, comercio). |
| **Categoría** | Grupo del gasto y conjunto de campos que pide el formulario. |
| **IVA incluido** | El importe escrito ya lleva el impuesto dentro. |
| **IVA + 16%** | El impuesto se suma al importe escrito. |
| **Recurrente** | Gasto que se repite cada mes. |
| **Snapshot / Acta** | Foto resumida de un ejercicio, guardada como histórico. |
| **Proyección** | Estimación de cómo terminará el mes o el año al ritmo actual. |
| **Pareto 80/20** | Qué pocas categorías concentran la mayor parte del gasto. |
| **Base de datos** | Archivo único donde se guardan todas las tablas (aquí, SQLite). |
| **Tabla / fila / columna** | Planilla / renglón / dato de ese renglón. |
| **ID** | Código único de una fila (como el número de una factura). |
| **WAL** | Bitácora temporal de SQLite (`-wal`): cambios recientes antes de integrarse. |
| **Campo personalizado** | Dato extra que define una categoría (texto, número, lista o sí/no). |
| **Respaldo JSON** | Archivo de texto con todos los datos, para copia o restauración. |

---

## 19. Rutina sugerida

**Cada compra:** Registrar → guardar. Si el ticket es una foto, OCR.

**Cada semana:** Dashboard (ritmo y proyección) y Análisis → Precios (si algo
subió).

**Cada mes:** revisar Compromisos recurrentes y el reparto por categoría; hacer
un **Respaldo JSON**.

**Cada año:** Reportes → revisar el Acta → **Descargar acta** → **Cerrar y
archivar ejercicio** (con o sin limpieza de las compras del año).
