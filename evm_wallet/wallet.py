import asyncio
from web3 import AsyncWeb3, Web3
from web3.middleware import geth_poa_middleware
from web3.types import Wei, TxParams, TxData
from hexbytes import HexBytes
from .exceptions import InvalidNetworkInfo
from .globals import NETWORK_MAP, ZERO_ADDRESS
from .types import AnyAddress, TokenAmount, Network, NetworkInfo, NetworkOrInfo
from eth_account import Account
from typing import Optional, Self, Union, cast
from eth_typing import ChecksumAddress, HexStr
from web3.contract.contract import ContractFunction
from .utils import _in_literal, load_token_contract, _has_keys


class AsyncWallet:
    """
    Async version of Wallet, interacting with your ethereum digital wallet.
    You can change a network of the wallet at any time using network setter
    """

    def __init__(
            self,
            private_key: str,
            network: NetworkOrInfo = 'Ethereum',
    ):
        """
        :param private_key: A private key of existing account
        :param network: Name of supported network to be interacted or custom information about network represented as
        type NetworkInfo
        """
        network_info = self.__validate_network(network)
        rpc = network_info['rpc']
        self.__network = network_info
        self.__provider = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc))

        temp_provider = Web3(Web3.HTTPProvider(rpc))

        self.__private_key = private_key
        self.__account = Account.from_key(private_key)
        self.__public_key = self.__provider.to_checksum_address(self.__account.address)
        self.__nonce = temp_provider.eth.get_transaction_count(self.__public_key)
        self.__chain_id = temp_provider.eth.chain_id

    @property
    def provider(self) -> AsyncWeb3:
        return self.__provider

    @property
    def network(self) -> NetworkInfo:
        """
        You can change a network of the wallet at any time using network setter
        :return: Dictionary containing information about the network
        """
        return self.__network

    @network.setter
    def network(self, value: NetworkOrInfo):
        network_info = self.__validate_network(value)
        rpc = network_info['rpc']
        self.__network = network_info
        self.__provider = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc))

        temp_provider = Web3(Web3.HTTPProvider(rpc))
        self.__nonce = temp_provider.eth.get_transaction_count(self.__public_key)
        self.__chain_id = temp_provider.eth.chain_id

    @property
    def private_key(self) -> str:
        """
        The private key of the current account
        :return: The private key of the current account
        """
        return self.__private_key

    @property
    def public_key(self) -> ChecksumAddress:
        """
        The public key of the current account
        :return: The public key of the current account
        """
        return self.__public_key

    @property
    def nonce(self) -> int:
        """
        The nonce of the current wallet.
        :return: The nonce of the current wallet
        """
        return self.__nonce

    @property
    def native_token(self) -> str:
        return self.network['token']

    def is_native_token(self, token: str | HexBytes) -> bool:
        """
        Returns true if token is native token of network

        :param token: Name of token or zero-address - 0x0000000000000000000000000000000000000000
        :return: True if token is native token of network
        """
        network = self.network
        native_token = network['token']

        if isinstance(token, HexBytes):
            token.hex()

        return (token.upper() == native_token or
                token.lower() == native_token or
                token == ZERO_ADDRESS)

    @classmethod
    def create(cls, network: NetworkOrInfo = 'Ethereum') -> Self:
        """
        Creates all-new digital wallet
        :param network: Name of supported network to be interacted or custom information about network represented as
        type NetworkInfo
        :return: An instance of AsyncWallet
        """
        network = cls.__validate_network(network)

        private_key = Account.create().key
        return cls(private_key, network)

    @staticmethod
    def __validate_network(network: NetworkOrInfo = 'Ethereum') -> NetworkInfo:
        if _in_literal(network, Network):
            network = cast(Network, network)
            network_info = NetworkInfo(network=network, **NETWORK_MAP[network])
            return network_info
        elif _has_keys(network, NetworkInfo):
            return cast(NetworkInfo, network)
        else:
            raise InvalidNetworkInfo(network)

    async def get_balance(self, to_wei: bool = False) -> float | Wei:
        """
        Returns the balance of the current account in ethereum or wei units.
        :param to_wei: Whether to convert balance to Wei units (default: False)
        :return: Balance of the current account in ethereum units
        """
        provider = self.provider
        balance = await provider.eth.get_balance(self.public_key)

        return balance if to_wei else provider.from_wei(balance, 'ether')

    async def estimate_gas(self, tx_params: TxParams) -> Wei:
        """
        Returns an estimating quantity of gas to perform transaction in Wei units
        :param tx_params: Params of built transaction
        :return: Estimated gas in Wei
        """
        provider = self.provider
        gas = Wei(int(await provider.eth.estimate_gas(tx_params)))
        return gas

    async def build_and_transact(
            self,
            closure: ContractFunction,
            value: TokenAmount = 0,
            gas: Optional[int] = None,
            gas_price: Optional[Wei] = None
    ) -> HexBytes:
        """
        If you don't need to check estimated gas or directly use transact, you can call build_and_transact. It's based on getting
        closure as argument. Closure is transaction's function, called with arguments. Notice that it has to be not built or
        awaited

        Usage Example
        ----------
            wallet = AsyncWallet(private_key)

            uniswap = provider.eth.contract(address=address, abi=abi)

            closure = uniswap.functions.swapExactETHForTokens(arg1, arg2, ...)

            await wallet.build_and_transact(closure, eth_amount)

        :param closure: Transaction's function, called with arguments. Notice that it has to be not built or awaited
        :param value: A quantity of network currency to be paid in Wei units
        :param gas: A quantity of gas to be spent
        :param gas_price: A price of gas in Wei units
        :return: Transaction's hash
        """
        tx_params = await self.build_transaction_params(value=value, gas=gas, gas_price=gas_price)
        tx_params = await closure.build_transaction(tx_params)

        if not gas:
            del tx_params['gas']
            gas = await self.estimate_gas(tx_params)
            tx_params['gas'] = gas

        return await self.transact(tx_params)

    async def approve(
            self,
            token: AnyAddress,
            contract_address: AnyAddress,
            token_amount: TokenAmount
    ) -> HexBytes:
        """
        Approves token usage for the specific contract
        :param token: An address of token
        :param contract_address: An address of contract that will be using token
        :param token_amount: A quantity of token to be spent in Wei units
        :return: Transaction hash
        """
        token = load_token_contract(self.provider, token)
        contract_address = self.provider.to_checksum_address(contract_address)
        return await self.build_and_transact(
            token.functions.approve(contract_address, token_amount)
        )

    async def build_transaction_params(
            self,
            value: TokenAmount,
            recipient: Optional[AnyAddress] = None,
            raw_data: Optional[Union[bytes, HexStr]] = None,
            gas: Optional[int] = None,
            gas_price: Optional[Wei] = None
    ) -> TxParams:
        """
        Returns transaction's params
        :param value: A quantity of network currency to be paid in Wei units
        :param recipient: An address of recipient
        :param raw_data: Transaction's data provided as HexStr or bytes
        :param gas: A quantity of gas to be spent
        :param gas_price: A price of gas in Wei units
        :return: Transaction's params
        """
        provider = self.provider

        tx_params = {
            'from': self.public_key,
            'chainId': self.__chain_id,
            'nonce': self.nonce,
            'value': value,
            'gas': gas if gas else Wei(250_000),
            'gasPrice': gas_price if gas_price else await provider.eth.gas_price,
        }

        if recipient:
            tx_params['to'] = self.provider.to_checksum_address(recipient)

        if raw_data:
            tx_params['data'] = raw_data

        return tx_params

    async def transact(self, tx_params: TxParams) -> HexBytes:
        """
        Performs transaction, using transaction data, which is got after building
        :param tx_params: Built transaction's params
        :return: Transaction's hash
        """
        provider = self.provider
        signed_transaction = provider.eth.account.sign_transaction(tx_params, self.private_key)
        tx_hash = await provider.eth.send_raw_transaction(signed_transaction.rawTransaction)
        self.__nonce += 1

        return tx_hash

    async def transfer(
            self,
            token: AnyAddress,
            recipient: AnyAddress,
            token_amount: TokenAmount,
            gas: Optional[Wei] = None,
            gas_price: Optional[Wei] = None
    ) -> HexBytes:
        """
        Transfers token amount to another wallet
        :param token: An address of token
        :param recipient: An address of the recipient
        :param token_amount: A quantity of token to be transferred in Wei units
        :param gas: A quantity of gas to be spent
        :param gas_price: A price of gas in Wei units
        :return: Transaction hash
        """
        token_contract = load_token_contract(self.provider, token)
        recipient = self.provider.to_checksum_address(recipient)
        closure = await token_contract.functions.transfer(recipient, token_amount)
        return await self.build_and_transact(closure, Wei(0), gas, gas_price)

    async def get_balance_of(self, token: AnyAddress, convert: bool = True) -> float:
        """
        Returns balance of specified token in ethereum or wei units
        :param token: An address of token
        :param convert: Whether to divide token balance by its decimals (default: True)
        :return: Balance of specified token in ethereum or wei units
        """
        token_contract = load_token_contract(self.provider, token)
        balance = await token_contract.functions.balanceOf(self.public_key).call()

        if convert:
            decimals = await self.get_decimals(token)
            balance /= 10**decimals

        return balance

    async def get_decimals(self, token: AnyAddress) -> int:
        """
        Returns decimals of specified token
        :param token: An address of token 
        :return: Decimals of specified token 
        """
        token = load_token_contract(self.provider, token)
        decimals = await token.functions.decimals().call()
        return decimals

    def get_transactions(self) -> list[TxData]:
        """
        Returns a list of transactions for the current wallet
        :return: List of transactions
        """
        provider = Web3(Web3.HTTPProvider(self.network['rpc']))
        provider.middleware_onion.inject(geth_poa_middleware, layer=0)

        block_number = provider.eth.block_number
        start_block = 0
        end_block = block_number

        public_key = self.public_key

        transactions = []
        for block in range(end_block, start_block - 1, -1):
            block_info = provider.eth.get_block(block, True)

            for tx in reversed(block_info['transactions']):
                if public_key.lower() in [tx['from'].lower(), tx['to'].lower()]:
                    transactions.append(tx)

        return transactions

    def get_explorer_url(self, transaction_hash: HexBytes) -> str:
        """
        Returns the explorer url for the given transaction hash
        :return: Explorer url for the given transaction
        """
        if isinstance(transaction_hash, HexBytes):
            transaction_hash = transaction_hash.hex()
        else:
            raise TypeError(f"Invalid transaction hash type: {type(transaction_hash)}")

        explorer_url = f'{self.network["explorer"]}/tx/{transaction_hash}'
        return explorer_url


class Wallet(AsyncWallet):
    """
    Interacts with your ethereum digital wallet.
    You can change a network of the wallet at any time using network setter
    """

    def __init__(
            self,
            private_key: str,
            network: NetworkOrInfo = 'Ethereum',
    ):
        """
        :param private_key: A private key of existing account
        :param network: Name of supported network to be interacted or custom information about network represented as
        type NetworkInfo
        """
        super().__init__(private_key, network)

    def get_balance(self, to_wei: bool = False) -> float | Wei:
        """
        Returns the balance of the current account in ethereum units.
        :return: Balance of the current account in ethereum units
        """
        async_method = super().get_balance
        return asyncio.run(async_method())

    def estimate_gas(self, tx_params: TxParams) -> Wei:
        """
        Returns an estimating quantity of gas to perform transaction in Wei units
        :param tx_params: Params of built transaction
        :return: Estimated gas in Wei
        """
        async_method = super().estimate_gas
        return asyncio.run(async_method(tx_params))

    def build_and_transact(
            self,
            closure: ContractFunction,
            value: Wei = 0,
            gas: Optional[int] = None,
            gas_price: Optional[Wei] = None
    ) -> HexBytes:
        """
        If you don't need to check estimated gas or directly use transact, you can call build_and_transact. It's based on getting
        closure as argument. Closure is transaction's function, called with arguments. Notice that it has to be not built or
        awaited

        Usage Example
        -------
            wallet = AsyncWallet(private_key)

            uniswap = provider.eth.contract(address=address, abi=abi)

            closure = uniswap.functions.swapExactETHForTokens(arg1, arg2, ...)

            await wallet.build_and_transact(closure, eth_amount)

        :param closure: Transaction's function, called with arguments. Notice that it has to be not built or awaited
        :param value: A quantity of network currency to be paid in Wei units
        :param gas: A quantity of gas to be spent
        :param gas_price: A price of gas in Wei units
        :return: Transaction's hash
        """
        async_method = super().build_and_transact
        return asyncio.run(async_method(closure, value, gas, gas_price))

    def approve(
            self,
            token: AnyAddress,
            contract_address: AnyAddress,
            token_amount: TokenAmount
    ) -> HexBytes:
        """
        Approves token usage for the specific contract
        :param token: An address of token
        :param contract_address: An address of contract that will be using token
        :param token_amount: A quantity of token to be spent in Wei units
        :return: Transaction hash
        """
        async_method = super().approve
        return asyncio.run(async_method(token, contract_address, token_amount))

    def build_transaction_params(
            self,
            value: Wei,
            recipient: Optional[AnyAddress] = None,
            raw_data: Optional[Union[bytes, HexStr]] = None,
            gas: Optional[int] = None,
            gas_price: Optional[Wei] = None
    ) -> TxParams:
        """
        Returns transaction's params
        :param value: A quantity of network currency to be paid in Wei units
        :param recipient: An address of recipient
        :param raw_data: Transaction's data provided as HexStr or bytes
        :param gas: A quantity of gas to be spent
        :param gas_price: A price of gas in Wei units
        :return: Transaction's params
        """
        async_method = super().build_transaction_params
        return asyncio.run(async_method(value, recipient, raw_data, gas, gas_price))

    def transact(self, tx_params: TxParams) -> HexBytes:
        """
        Performs transaction, using transaction data, which is got after building
        :param tx_params: Built transaction's params
        :return: Transaction's hash
        """
        async_method = super().transact
        return asyncio.run(async_method(tx_params))

    def transfer(
            self,
            token: AnyAddress,
            recipient: AnyAddress,
            token_amount: TokenAmount,
            gas: Optional[Wei] = None,
            gas_price: Optional[Wei] = None
    ) -> HexBytes:
        """
        Transfers token amount to another wallet
        :param token: An address of token
        :param recipient: An address of the recipient
        :param token_amount: A quantity of token to be transferred in Wei units
        :param gas: A quantity of gas to be spent
        :param gas_price: A price of gas in Wei units
        :return: Transaction hash
        """
        async_method = super().transfer
        return asyncio.run(async_method(token, recipient, token_amount, gas, gas_price))

    def get_balance_of(self, token: AnyAddress, convert: bool = False) -> float:
        """
        Returns balance of specified token in ethereum or wei units
        :param token: An address of token
        :param convert: Whether to divide token balance by its decimals (default: False)
        :return: Balance of specified token in ethereum or wei units
        """
        async_method = super().get_balance_of
        return asyncio.run(async_method(token))

    def get_decimals(self, token: AnyAddress) -> int:
        """
        Returns decimals of specified token
        :param token: An address of token
        :return: Decimals of specified token
        """
        async_method = super().get_decimals
        return asyncio.run(async_method(token))
