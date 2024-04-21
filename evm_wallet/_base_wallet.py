import json
import os
from functools import lru_cache
from typing import ClassVar, cast, Self, Optional
from eth_account import Account
from eth_typing import ChecksumAddress, HexStr
from abc import ABC, abstractmethod
from hexbytes import HexBytes
from web3 import AsyncWeb3, Web3
from web3.contract.contract import ContractFunction, Contract
from web3.contract.async_contract import AsyncContract, AsyncContractFunction
from web3.types import ABI, Wei, TxParams
from evm_wallet.types import Network, NetworkInfo, AnyAddress, TokenAmount, ERC20Token
from evm_wallet.utils import _in_literal, _has_keys

ZERO_ADDRESS = Web3.to_checksum_address("0x0000000000000000000000000000000000000000")


class _BaseWallet(ABC):
    __network_map: ClassVar[dict[Network, NetworkInfo]] = {
        'Arbitrum Goerli': {
            'chain_id': 421613,
            'rpc': 'wss://arbitrum-goerli-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://goerli.arbiscan.io'
        },
        'Arbitrum Sepolia': {
            'chain_id': 421614,
            'rpc': 'wss://arbitrum-sepolia-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://sepolia.arbiscan.io'
        },
        'Arbitrum': {
            'chain_id': 42161,
            'rpc': 'wss://arbitrum-one-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://arbiscan.io'
        },
        'Avalanche': {
            'chain_id': 43114,
            'rpc': 'wss://avalanche-c-chain-rpc.publicnode.com',
            'token': 'AVAX',
            'explorer': 'https://snowtrace.io/'
        },
        'Base': {
            'chain_id': 8453,
            'rpc': 'wss://base-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://basescan.org/'
        },
        'Base Goerli': {
            'chain_id': 84531,
            'rpc': 'https://base-goerli.public.blastapi.io',
            'token': 'ETH',
            'explorer': 'https://goerli.basescan.org/'
        },
        'Base Sepolia': {
            'chain_id': 84532,
            'rpc': 'wss://base-sepolia-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://sepolia.basescan.org/'
        },
        'BSC': {
            'chain_id': 56,
            'rpc': 'wss://bsc-rpc.publicnode.com',
            'token': 'BNB',
            'explorer': 'https://bscscan.com'
        },
        'BSC Testnet': {
            'chain_id': 97,
            'rpc': 'wss://bsc-testnet-rpc.publicnode.com',
            'token': 'BNB',
            'explorer': 'https://testnet.bscscan.com'
        },
        'Ethereum': {
            'chain_id': 1,
            'rpc': 'wss://ethereum-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://etherscan.io'
        },
        'Fantom': {
            'chain_id': 250,
            'rpc': 'wss://fantom-rpc.publicnode.com',
            'token': 'FTM',
            'explorer': 'https://ftmscan.com/'
        },
        'Fantom Testnet': {
            'chain_id': 4002,
            'rpc': 'wss://fantom-testnet-rpc.publicnode.com',
            'token': 'FTM',
            'explorer': 'https://testnet.ftmscan.com/'
        },
        'Fuji': {
            'chain_id': 43113,
            'rpc': 'wss://avalanche-fuji-c-chain-rpc.publicnode.com',
            'token': 'AVAX',
            'explorer': 'https://testnet.snowtrace.io'
        },
        'Goerli': {
            'chain_id': 5,
            'rpc': 'wss://goerli.gateway.tenderly.co',
            'token': 'ETH',
            'explorer': 'https://goerli.etherscan.io'
        },
        'Linea': {
            'chain_id': 59144,
            'rpc': 'wss://linea.drpc.org',
            'token': 'ETH',
            'explorer': 'https://lineascan.build/'
        },
        'Linea Goerli': {
            'chain_id': 59140,
            'rpc': 'wss://linea-goerli.drpc.org',
            'token': 'ETH',
            'explorer': 'https://goerli.lineascan.build/'
        },
        'Mumbai': {
            'chain_id': 80001,
            'rpc': 'wss://polygon-mumbai-bor-rpc.publicnode.com',
            'token': 'MATIC',
            'explorer': 'https://mumbai.polygonscan.com/'
        },
        'opBNB': {
            'chaind_id': 204,
            'rpc': 'wss://opbnb-rpc.publicnode.com',
            'token': 'BNB',
            'explorer': 'https://opbnb.bscscan.com/'
        },
        'opBNB Testnet': {
            'chaind_id': 5611,
            'rpc': 'wss://opbnb-testnet-rpc.publicnode.com',
            'token': 'BNB',
            'explorer': 'https://opbnb-testnet.bscscan.com'
        },
        'Optimism': {
            'chain_id': 10,
            'rpc': 'wss://optimism-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://optimistic.etherscan.io'
        },
        'Optimism Sepolia': {
            'chaind_id': 11155420,
            'rpc': 'wss://optimism-sepolia-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://sepolia-optimism.etherscan.io/'
        },
        'Optimism Goerli': {
            'chain_id': 420,
            'rpc': 'wss://optimism-testnet.drpc.org',
            'token': 'ETH',
            'explorer': 'https://goerli-optimism.etherscan.io'
        },
        'Polygon': {
            'chain_id': 137,
            'rpc': 'wss://polygon-bor-rpc.publicnode.com',
            'token': 'MATIC',
            'explorer': 'https://polygonscan.com'
        },
        'Sepolia': {
            'chain_id': 11155111,
            'rpc': 'wss://ethereum-sepolia-rpc.publicnode.com',
            'token': 'ETH',
            'explorer': 'https://sepolia.etherscan.io'
        },
        'Scroll': {
          'chaind_id': 534352,
          'rpc': 'wss://scroll.drpc.org',
          'token': 'ETH',
          'explorer': 'https://scrollscan.com'
        },
        'zkSync': {
            'chain_id': 324,
            'rpc': 'wss://zksync.drpc.org',
            'token': 'ETH',
            'explorer': 'https://explorer.zksync.io'
        }
    }

    def __init__(
            self,
            private_key: str,
            network: Network | NetworkInfo,
            is_async: bool = False
    ):
        network_info = self.__validate_network(network)
        rpc = network_info['rpc']

        is_websocket_rpc = rpc.startswith('wss://')

        if is_websocket_rpc:
            temp_provider = Web3(Web3.WebsocketProvider(rpc))
        else:
            temp_provider = Web3(Web3.HTTPProvider(rpc))

        if is_async:
            if is_websocket_rpc:
                self._provider = AsyncWeb3(AsyncWeb3.WebsocketProvider(rpc))
            else:
                self._provider = AsyncWeb3(AsyncWeb3.HTTPProvider(rpc))
        else:
            self._provider = temp_provider

        self.__validate_chain_id(network_info, temp_provider)

        self.__private_key = private_key
        self.__account = Account.from_key(private_key)
        self.__public_key = self._provider.to_checksum_address(self.__account.address)
        self.__nonce = temp_provider.eth.get_transaction_count(self.__public_key)

        self.__network = network_info

    @classmethod
    def create(cls, network: Network | NetworkInfo = 'Ethereum') -> Self:
        """
        Creates all-new digital wallet
        :param network: Name of supported network to be interacted or custom information about network represented as
        type NetworkInfo
        :return: Instance of AsyncWallet
        """
        private_key = Account.create().key
        return cls(private_key, network)

    @property
    def provider(self) -> AsyncWeb3 | Web3:
        """

        :return:
        """
        return self._provider

    @property
    def network(self) -> NetworkInfo:
        """
        Current network. You can change the network of the wallet at any time using network setter
        :return: Dictionary containing information about the network represented as type NetworkInfo
        """
        return self.__network

    @network.setter
    def network(self, value: Network | NetworkInfo):
        """
        Change the network of the wallet
        :param value: Name of supported network to be interacted or custom information about network represented as
                      type NetworkInfo
        :return: None
        """
        network_info = self.__validate_network(value)
        rpc = network_info['rpc']
        self.__network = network_info
        self._provider = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(rpc))

        temp_provider = Web3(Web3.HTTPProvider(rpc))
        self.__nonce = temp_provider.eth.get_transaction_count(self.__public_key)

    @property
    def private_key(self) -> str:
        """
        Private key of the current account
        :return: Private key of the current account
        """
        return self.__private_key

    @property
    def public_key(self) -> ChecksumAddress:
        """
        Public key of the current account
        :return: Public key of the current account
        """
        return self.__public_key

    @property
    def nonce(self) -> int:
        """
        Nonce of the current wallet.
        :return: Nonce of the current wallet
        """
        return self.__nonce

    @property
    def native_token(self) -> str:
        return self.network['token']

    @classmethod
    def get_network_map(cls) -> dict[Network, NetworkInfo]:
        return cls.__network_map

    def is_native_token(self, token: str | AnyAddress) -> bool:
        """
        Returns true if token is native token of network

        :param token: Symbol of token or zero-address - 0x0000000000000000000000000000000000000000
        :return: True if token is native token of network
        """
        network = self.network
        native_token = network['token']

        if isinstance(token, bytes):
            token.hex()

        return (token.upper() == native_token or
                token.lower() == native_token or
                token == ZERO_ADDRESS)

    @classmethod
    def __validate_network(
            cls,
            network: Network | NetworkInfo
    ) -> NetworkInfo:
        if _in_literal(network, Network):
            network = cast(Network, network)
            network_info = NetworkInfo(network=network, **cls.__network_map[network])
        elif _has_keys(network, NetworkInfo):
            network_info = cast(NetworkInfo, network)
        else:
            raise TypeError(f"Network information must be represented as NetworkInfo type or name of a supported "
                            f"network. You provided value: {network}")

        return network_info

    @classmethod
    def __validate_chain_id(cls, network_info: NetworkInfo, provider: Web3) -> NetworkInfo:
        chain_id = provider.eth.chain_id
        if network_info['chain_id'] is not None and chain_id != network_info['chain_id']:
            raise ValueError(f'Chain id in network info must be equal to the chain. Try to find it by: '
                             f'https://chainlist.org/?search={network_info["network"].lower()}')
        else:
            network_info['chain_id'] = chain_id

        return network_info

    @staticmethod
    @lru_cache()
    def _get_erc20_abi() -> ABI:
        abs_path = os.path.dirname(os.path.abspath(__file__))
        path = f"{abs_path}/erc20.abi"
        with open(path) as file:
            return json.load(file)

    @lru_cache(maxsize=6)
    def _load_token_contract(self, address: AnyAddress) -> AsyncContract | Contract:
        if isinstance(address, bytes):
            address = address.hex()

        provider = self.provider
        address = provider.to_checksum_address(address)
        abi = self._get_erc20_abi()
        contract = provider.eth.contract(address=address, abi=abi)
        return contract

    def get_explorer_url(self, tx_hash: HexBytes | str) -> str:
        """
        Returns the explorer url for the given transaction hash
        :return: Explorer url for the given transaction
        """
        if isinstance(tx_hash, bytes):
            tx_hash = tx_hash.hex()
        elif not isinstance(tx_hash, str):
            raise TypeError(f"Invalid transaction hash type: {type(tx_hash)}")

        explorer_url = f'{self.network["explorer"]}/tx/{tx_hash}'
        return explorer_url

    @abstractmethod
    def get_token(self, address: AnyAddress) -> ERC20Token:
        pass

    @abstractmethod
    def get_balance(self, to_wei: bool = True) -> float | Wei:
        pass

    @abstractmethod
    def estimate_gas(self, tx_params: TxParams) -> Wei:
        pass

    @abstractmethod
    def build_and_transact(
            self,
            closure: ContractFunction | AsyncContractFunction,
            value: TokenAmount = 0,
            gas: Optional[int] = None,
            gas_price: Optional[Wei] = None
    ) -> HexBytes:
        pass

    @abstractmethod
    def approve(
            self,
            token: ERC20Token,
            contract_address: AnyAddress,
            token_amount: TokenAmount
    ) -> HexBytes:
        pass

    @abstractmethod
    def build_tx_params(
            self,
            value: TokenAmount,
            recipient: Optional[AnyAddress] = None,
            raw_data: Optional[bytes | HexStr] = None,
            gas: Optional[Wei] = Wei(300_000),
            gas_price: Optional[Wei] = None
    ) -> TxParams:
        pass

    @abstractmethod
    def transact(self, tx_params: TxParams) -> HexBytes:
        pass

    @abstractmethod
    def transfer(
            self,
            token: ERC20Token,
            recipient: AnyAddress,
            token_amount: TokenAmount,
            gas: Optional[Wei] = None,
            gas_price: Optional[Wei] = None
    ) -> HexBytes:
        pass

    @abstractmethod
    def get_balance_of(self, token: ERC20Token, convert: bool = False) -> float:
        pass
