from decimal import Decimal
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlmodel import Session, select

from .conftest import make_user, new_category, new_product, sign_in, sku_row

from opname360.models import ActivityLog, Role, Sku
from opname360.services.product_import import ANGLE


PRODUCTS = '/api/v1/products/'
HEADER = [
    'Kategori',
    'Sub-kategori',
    'Nama produk',
    'Ukuran',
    'Warna',
    'Satuan',
    'Harga jual',
    'Barcode',
    'Kode',
    'Kemasan beli',
    'Isi kemasan',
    'Harga beli terakhir',
]


def xlsx(*rows: list[object], header: list[str] = HEADER) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def upload(
    client: TestClient, url: str, data: bytes, name: str = 'katalog.xlsx'
):
    return client.post(url, files={'file': (name, data)})


SHOP = xlsx(
    ['Seragam', 'Kemeja', 'Kemeja Putih SD', '10', None, None, 85000],
    ['Seragam', 'Kemeja', 'Kemeja Putih SD', '12', None, None, 'Rp 90.000'],
    [
        'Seragam',
        'Topi',
        'Topi SD',
        None,
        'Merah',
        'pcs',
        25000,
        None,
        None,
        None,
        None,
        15000,
    ],
    [None, None, None],
    [
        'ATK',
        'Pulpen',
        'Pulpen Biru',
        None,
        None,
        'pcs',
        3000,
        8991234567890.0,
        'PLP-B',
        'box',
        12,
        '2.500',
    ],
)


def test_preview_counts_products_and_new_categories_without_saving(
    owner_client: TestClient,
) -> None:
    new_category(owner_client, 'Seragam', ('Kemeja',))

    preview = upload(owner_client, f'{PRODUCTS}import/preview', SHOP).json()

    assert preview['problems'] == []
    assert preview['product_count'] == 3
    assert preview['sku_count'] == 4
    assert preview['new_categories'] == ['ATK']
    assert preview['new_sub_categories'] == [
        f'Seragam {ANGLE} Topi',
        f'ATK {ANGLE} Pulpen',
    ]
    assert owner_client.get(PRODUCTS).json()['total'] == 0


def test_import_creates_products_grouping_rows_into_skus(
    owner_client: TestClient, session: Session
) -> None:
    result = upload(owner_client, f'{PRODUCTS}import', SHOP)

    assert result.status_code == 200, result.text
    assert result.json() == {
        'product_count': 3,
        'sku_count': 4,
        'category_count': 2,
        'sub_category_count': 3,
    }
    products = {
        product['name']: product
        for product in owner_client.get(PRODUCTS).json()['items']
    }
    shirt = products['Kemeja Putih SD']
    assert shirt['category_name'] == 'Seragam'
    assert [(sku['size'], sku['selling_price']) for sku in shirt['skus']] == [
        ('10', 85000),
        ('12', 90000),
    ]
    pen = products['Pulpen Biru']['skus'][0]
    assert pen['barcode'] == '8991234567890'
    assert pen['code'] == 'PLP-B'
    assert pen['purchase_pack_name'] == 'box'
    assert Decimal(pen['purchase_pack_size']) == 12
    assert Decimal(pen['latest_unit_cost']) == 2500
    hat = products['Topi SD']['skus'][0]
    assert hat['color'] == 'Merah'
    assert hat['barcode'] == f'2{hat["id"]:07d}'
    assert Decimal(hat['latest_unit_cost']) == 15000
    logged = session.exec(
        select(ActivityLog).where(ActivityLog.action == 'product.import')
    ).one()
    assert logged.summary == 'Mengimpor 3 produk (4 SKU) dari katalog.xlsx.'


def test_a_file_with_any_problem_imports_nothing_and_lists_every_one(
    owner_client: TestClient,
) -> None:
    bad = xlsx(
        ['Seragam', 'Kemeja', 'Kemeja Putih SD', '10', None, None, 85000],
        ['Seragam', 'Kemeja', 'Kemeja Putih SD', '10', None, None, 85000],
        ['Seragam', 'Kemeja', None, None, None, None, 'gratis'],
        [
            'ATK',
            'Pulpen',
            'Pulpen',
            None,
            None,
            None,
            3000,
            '111',
            None,
            'box',
        ],
        ['ATK', 'Pulpen', 'Pensil', None, None, None, -5, '111'],
    )

    preview = upload(owner_client, f'{PRODUCTS}import/preview', bad).json()
    result = upload(owner_client, f'{PRODUCTS}import', bad)

    assert [
        (problem['row'], problem['column']) for problem in preview['problems']
    ] == [
        (3, 'Ukuran'),
        (4, 'Nama produk'),
        (4, 'Harga jual'),
        (5, 'Kemasan beli'),
        (6, 'Harga jual'),
        (6, 'Barcode'),
    ]
    assert 'baris 2' in preview['problems'][0]['message']
    assert result.status_code == 409
    assert owner_client.get(PRODUCTS).json()['total'] == 0
    assert owner_client.get('/api/v1/categories/').json() == []


def test_codes_already_in_the_catalogue_are_refused(
    owner_client: TestClient,
) -> None:
    sub_category = new_category(owner_client, 'Seragam', ('Kemeja',))[
        'sub_categories'
    ][0]['id']
    new_product(
        owner_client,
        sub_category,
        'Kemeja Putih SD',
        [sku_row(barcode='8990001', code='KMJ-1')],
    )
    clashing = xlsx(
        ['Seragam', 'Kemeja', 'Kemeja Putih SD', '14', None, None, 1],
        ['ATK', 'Pulpen', 'Pulpen', None, None, None, 1, '8990001', 'kmj-1'],
    )

    problems = upload(
        owner_client, f'{PRODUCTS}import/preview', clashing
    ).json()['problems']

    assert [(p['row'], p['column']) for p in problems] == [
        (2, 'Nama produk'),
        (3, 'Barcode'),
        (3, 'Kode'),
    ]
    assert problems[0]['message'] == (
        'Produk Kemeja Putih SD sudah ada di Kemeja. Ubah lewat menu Produk.'
    )
    assert problems[1]['message'] == (
        '8990001 sudah dipakai oleh Kemeja Putih SD (10).'
    )


def test_a_file_without_the_required_columns_is_refused(
    owner_client: TestClient,
) -> None:
    wrong = xlsx(['x'], header=['Nama', 'Harga'])

    problems = upload(owner_client, f'{PRODUCTS}import/preview', wrong).json()[
        'problems'
    ]

    assert {p['column'] for p in problems} == {
        'Kategori',
        'Sub-kategori',
        'Nama produk',
        'Harga jual',
    }


def test_a_file_that_is_not_excel_is_refused(owner_client: TestClient) -> None:
    preview = upload(
        owner_client, f'{PRODUCTS}import/preview', b'nama,harga\n', 'x.csv'
    ).json()

    assert preview['problems'][0]['message'] == (
        'File ini bukan file Excel (.xlsx) yang bisa dibaca.'
    )


def test_an_empty_file_imports_nothing(owner_client: TestClient) -> None:
    assert upload(owner_client, f'{PRODUCTS}import', xlsx()).status_code == 409


def test_the_template_has_the_columns_and_a_guide(
    owner_client: TestClient,
) -> None:
    response = owner_client.get(f'{PRODUCTS}import/template')

    assert response.status_code == 200
    assert (
        'template-impor-produk.xlsx' in response.headers['content-disposition']
    )
    workbook = load_workbook(BytesIO(response.content))
    assert workbook.sheetnames == ['Produk', 'Petunjuk']
    header = [cell.value for cell in workbook['Produk'][1]]
    assert header == HEADER
    # The template itself passes the import's checks.
    preview = upload(
        owner_client, f'{PRODUCTS}import/preview', response.content
    ).json()
    assert preview['problems'] == []
    assert preview['sku_count'] == 0


def test_a_cashier_cannot_import(client: TestClient, session: Session) -> None:
    make_user(session, 'kasir', Role.cashier)
    sign_in(client, 'kasir')

    assert upload(client, f'{PRODUCTS}import', SHOP).status_code == 403


def test_skus_for_labels_come_back_in_the_order_asked(
    owner_client: TestClient, session: Session
) -> None:
    upload(owner_client, f'{PRODUCTS}import', SHOP)
    ids = sorted(sku.id for sku in session.exec(select(Sku)).all() if sku.id)

    asked = [ids[2], ids[0], 9999, ids[2]]
    skus = owner_client.get(f'{PRODUCTS}skus', params={'ids': asked}).json()

    assert [sku['id'] for sku in skus] == [ids[2], ids[0]]
    assert skus[0]['product_name'] == 'Topi SD'
    assert skus[0]['selling_price'] == 25000
