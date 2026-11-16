"""Slice 2, rules 1-8: opening a Stock Opname and counting blind."""

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from .conftest import (
    COUNTING,
    OPNAMES,
    count,
    lines_of,
    make_user,
    new_category,
    new_product,
    new_sku,
    open_opname,
    receive,
    sku_row,
    switch_to,
)

from opname360.core.formatting import ANGLE
from opname360.models import (
    ActivityLog,
    OpnameLine,
    Role,
    Sku,
    UnknownBarcode,
    User,
)


def line_of(session: Session, opname_id: int, sku: Sku) -> OpnameLine:
    line = session.exec(
        select(OpnameLine).where(
            OpnameLine.opname_id == opname_id, OpnameLine.sku_id == sku.id
        )
    ).one()
    session.refresh(line)
    return line


# Rule 1


def test_opening_takes_every_active_sku_and_inactive_ones_with_stock(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    active = new_sku(owner_client, session)
    inactive_with_stock = new_sku(owner_client, session)
    receive(owner_client, inactive_with_stock, 3, 1000)
    inactive_without_stock = new_sku(owner_client, session)
    for sku in (inactive_with_stock, inactive_without_stock):
        sku.is_active = False
        session.add(sku)
    session.commit()
    checker = make_user(session, 'budi', Role.cashier)

    opname = open_opname(owner_client, [checker])

    assert opname['number'].startswith('SO-')
    assert opname['status'] == 'counting'
    assert opname['scope_label'] == 'Semua SKU'
    sku_ids = {line['sku_id'] for line in lines_of(owner_client, opname['id'])}
    assert sku_ids == {active.id, inactive_with_stock.id}
    assert opname['line_count'] == 2
    assert opname['checkers'] == [
        {'id': checker.id, 'full_name': 'Budi', 'role': 'cashier'}
    ]
    logged = session.exec(
        select(ActivityLog).where(ActivityLog.action == 'stock_opname.open')
    ).one()
    assert opname['number'] in logged.summary


def test_scope_by_category_sub_category_or_chosen_skus(
    owner_client: TestClient, session: Session
) -> None:
    seragam = new_category(owner_client, 'Seragam', ('Kemeja', 'Topi'))
    kemeja, topi = (sub['id'] for sub in seragam['sub_categories'])
    shirt = new_product(owner_client, kemeja, 'Kemeja', [sku_row()])
    hat = new_product(owner_client, topi, 'Topi SD', [sku_row()])
    atk = new_category(owner_client, 'ATK', ('Pulpen',))
    pen = new_product(
        owner_client, atk['sub_categories'][0]['id'], 'Pulpen', [sku_row()]
    )
    checker = make_user(session, 'budi', Role.cashier)

    def scoped(**body: object) -> tuple[str, set[int]]:
        opname = open_opname(owner_client, [checker], **body)
        sku_ids = {
            line['sku_id'] for line in lines_of(owner_client, opname['id'])
        }
        owner_client.post(f'{OPNAMES}{opname["id"]}/cancel')
        return opname['scope_label'], sku_ids

    shirt_id, hat_id, pen_id = (
        product['skus'][0]['id'] for product in (shirt, hat, pen)
    )
    assert scoped(scope='categories', category_ids=[seragam['id']]) == (
        'Seragam',
        {shirt_id, hat_id},
    )
    assert scoped(scope='sub_categories', sub_category_ids=[topi]) == (
        f'Seragam {ANGLE} Topi',
        {hat_id},
    )
    assert scoped(scope='skus', sku_ids=[pen_id, shirt_id]) == (
        '2 SKU pilihan',
        {pen_id, shirt_id},
    )
    response = owner_client.post(
        OPNAMES, json={'checker_ids': [checker.id], 'scope': 'categories'}
    )
    assert response.status_code == 400
    assert response.json()['detail'] == 'Pilih minimal satu kategori.'


# Rule 2


def test_a_sku_is_in_only_one_unfinished_opname_per_location(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    other = new_sku(owner_client, session)
    checker = make_user(session, 'budi', Role.cashier)
    first = open_opname(
        owner_client, [checker], scope='skus', sku_ids=[sku.id]
    )

    response = owner_client.post(
        OPNAMES,
        json={
            'checker_ids': [checker.id],
            'scope': 'skus',
            'sku_ids': [sku.id, other.id],
        },
    )
    assert response.status_code == 409
    assert first['number'] in response.json()['detail']
    # A different SKU is fine, and so is the same one once the first is
    # cancelled.
    open_opname(owner_client, [checker], scope='skus', sku_ids=[other.id])
    owner_client.post(f'{OPNAMES}{first["id"]}/cancel')
    open_opname(owner_client, [checker], scope='skus', sku_ids=[sku.id])


# Rule 3


def test_only_assigned_checkers_count_and_any_role_can_be_one(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    cashier = make_user(session, 'budi', Role.cashier)
    outsider = make_user(session, 'sari', Role.admin)
    opname = open_opname(owner_client, [cashier])

    # Not even the Owner counts without being assigned.
    response = count(owner_client, opname['id'], sku_id=sku.id)
    assert response.status_code == 403
    switch_to(owner_client, outsider)
    assert count(owner_client, opname['id'], sku_id=sku.id).status_code == 403
    assert owner_client.get(COUNTING).json() == []

    switch_to(owner_client, cashier)
    sessions = owner_client.get(COUNTING).json()
    assert [s['number'] for s in sessions] == [opname['number']]
    assert sessions[0]['can_count'] is True
    response = count(owner_client, opname['id'], sku_id=sku.id)
    assert response.status_code == 201, response.text
    # A Cashier still has no back office.
    assert owner_client.get(OPNAMES).status_code == 403


# Rule 4


def test_blind_count_sends_no_system_quantity_before_review(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    receive(owner_client, sku, 10, 1000)
    checker = make_user(session, 'budi', Role.admin)
    opname = open_opname(owner_client, [checker])
    switch_to(owner_client, checker)
    count(owner_client, opname['id'], sku_id=sku.id, quantity=7)

    sheet = owner_client.get(f'{COUNTING}{opname["id"]}').json()
    assert sheet['entries'][0]['quantity'] == '7.000'
    assert 'system_quantity' not in str(sheet)

    # The Admin who counts sees only which lines are counted, even through
    # the back office.
    detail = owner_client.get(f'{OPNAMES}{opname["id"]}').json()
    assert detail['revealed'] is False
    assert detail['shortage_value'] is None
    [line] = lines_of(owner_client, opname['id'])
    assert line['counted'] is True
    assert line['system_quantity'] is None
    assert line['physical_quantity'] is None
    assert line['variance'] is None
    response = owner_client.get(
        f'{OPNAMES}{opname["id"]}/lines', params={'show': 'variance'}
    )
    assert response.status_code == 403

    # And so does the Owner, until counting is closed.
    switch_to(owner_client, owner)
    [line] = lines_of(owner_client, opname['id'])
    assert line['system_quantity'] is None


# Rules 5 and 6


def test_counts_add_up_against_the_first_counts_snapshot(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    receive(owner_client, sku, 5, 1000)
    budi = make_user(session, 'budi', Role.cashier)
    sari = make_user(session, 'sari', Role.cashier)
    opname = open_opname(owner_client, [budi, sari])

    switch_to(owner_client, budi)
    # On display: two scans and a typed 1.
    assert (
        count(owner_client, opname['id'], code=sku.barcode).status_code == 201
    )
    assert count(owner_client, opname['id'], code=sku.code).status_code == 201
    count(owner_client, opname['id'], sku_id=sku.id, quantity=1)
    line = line_of(session, opname['id'], sku)
    assert line.system_quantity == 5
    assert line.physical_quantity == 3

    # More arrives; the snapshot stays at 5.
    switch_to(owner_client, owner)
    receive(owner_client, sku, 4, 1000)
    # In the storeroom, the other Checker finds 2.
    switch_to(owner_client, sari)
    count(owner_client, opname['id'], sku_id=sku.id, quantity=2)

    line = line_of(session, opname['id'], sku)
    assert line.system_quantity == 5
    assert line.physical_quantity == 5
    sheet = owner_client.get(f'{COUNTING}{opname["id"]}').json()
    assert (sheet['entry_count'], sheet['sku_count']) == (1, 1)


def test_a_checker_takes_back_their_own_entry(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    budi = make_user(session, 'budi', Role.cashier)
    sari = make_user(session, 'sari', Role.cashier)
    opname = open_opname(owner_client, [budi, sari])
    switch_to(owner_client, budi)
    entry = count(owner_client, opname['id'], code=sku.barcode).json()
    url = f'{COUNTING}{opname["id"]}/entries/{entry["id"]}'

    switch_to(owner_client, sari)
    assert owner_client.delete(url).status_code == 404
    switch_to(owner_client, budi)
    assert owner_client.delete(url).status_code == 204

    # Nothing left on the line: uncounted again, with no snapshot.
    line = line_of(session, opname['id'], sku)
    assert line.first_counted_at is None
    assert line.system_quantity is None
    assert line.physical_quantity == 0
    sheet = owner_client.get(f'{COUNTING}{opname["id"]}').json()
    assert sheet['entries'] == []


# Rule 7


def test_barcodes_outside_the_scope_or_unknown_are_refused(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    elsewhere = new_sku(owner_client, session)
    checker = make_user(session, 'budi', Role.cashier)
    opname = open_opname(
        owner_client, [checker], scope='skus', sku_ids=[sku.id]
    )
    switch_to(owner_client, checker)

    response = count(owner_client, opname['id'], code=elsewhere.barcode)
    assert response.status_code == 409
    assert 'tidak termasuk opname ini' in response.json()['detail']

    response = count(owner_client, opname['id'], code='8991234567890')
    assert response.status_code == 404
    assert 'dicatat untuk Admin' in response.json()['detail']
    count(owner_client, opname['id'], code='8991234567890')

    switch_to(owner_client, owner)
    detail = owner_client.get(f'{OPNAMES}{opname["id"]}').json()
    [unknown] = detail['unknown_barcodes']
    assert unknown['code'] == '8991234567890'
    assert unknown['times'] == 2
    assert unknown['last_scanned_by_name'] == 'Budi'
    assert detail['counted_count'] == 0
    assert session.exec(select(UnknownBarcode)).all()


def test_find_skus_in_scope_by_name(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    elsewhere = new_sku(owner_client, session)
    checker = make_user(session, 'budi', Role.cashier)
    opname = open_opname(
        owner_client, [checker], scope='skus', sku_ids=[sku.id]
    )
    switch_to(owner_client, checker)

    found = owner_client.get(
        f'{COUNTING}{opname["id"]}/skus', params={'search': 'Produk'}
    ).json()
    assert [option['id'] for option in found] == [sku.id]
    assert elsewhere.id not in [option['id'] for option in found]


# Rule 8


def test_a_line_whose_sku_moved_between_counts_is_flagged(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    moved = new_sku(owner_client, session)
    still = new_sku(owner_client, session)
    checker = make_user(session, 'budi', Role.cashier)
    opname = open_opname(owner_client, [checker])
    switch_to(owner_client, checker)
    count(owner_client, opname['id'], sku_id=moved.id, quantity=3)
    count(owner_client, opname['id'], sku_id=still.id, quantity=3)

    switch_to(owner_client, owner)
    receive(owner_client, moved, 2, 1000)

    switch_to(owner_client, checker)
    count(owner_client, opname['id'], sku_id=moved.id, quantity=2)
    count(owner_client, opname['id'], sku_id=still.id, quantity=2)
    assert line_of(session, opname['id'], moved).moved_while_counting
    assert not line_of(session, opname['id'], still).moved_while_counting


def test_counted_lines_are_listed_by_state(
    owner_client: TestClient, session: Session
) -> None:
    counted = new_sku(owner_client, session)
    uncounted = new_sku(owner_client, session)
    checker = make_user(session, 'budi', Role.cashier)
    opname = open_opname(owner_client, [checker])
    switch_to(owner_client, checker)
    count(owner_client, opname['id'], sku_id=counted.id, quantity=1)

    switch_to(owner_client, make_user(session, 'sari', Role.owner))
    by_state = {
        show: [
            line['sku_id']
            for line in lines_of(owner_client, opname['id'], show=show)
        ]
        for show in ('counted', 'uncounted')
    }
    assert by_state == {'counted': [counted.id], 'uncounted': [uncounted.id]}
    listed = owner_client.get(OPNAMES).json()
    assert listed['items'][0]['counted_count'] == 1
    assert listed['items'][0]['line_count'] == 2
    assert session.exec(
        select(OpnameLine).where(col(OpnameLine.opname_id) == opname['id'])
    ).all()
