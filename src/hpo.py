"""
Defines a training function to take a configuration, train, and return results.
"""

import torch
import wandb

from data.data_prep_tinyshakespeare import (
        extract_vocab_and_data, create_text_encoder_decoder, create_data_splits, get_batch
    )
from src.char_lm import setup_model, setup_training
from src.utils import count_trainable_params, train_and_evaluate_model, load_config



def prepare_shakespeare(train_size=0.9, input_path="data/tinyshakespeare/input.txt"):
    vocab, text = extract_vocab_and_data(input_path)
    vocab_size = len(vocab)
    encode, decode = create_text_encoder_decoder(vocab)
    data, train_data, valid_data = create_data_splits(text, train_size, encode, decode)

    shakespeare = dict(
        vocab=vocab,
        vocab_size=len(vocab),
        train_data=train_data,
        valid_data=valid_data,
    )
    return shakespeare


def exp_setup(setup_args=None):
    if setup_args is None:
        setup_args = load_config("setup_charLM-default")
    if "device" not in setup_args or setup_args["device"] is None:
        setup_args["device"] = "cuda" if torch.cuda.is_available() else "cpu"
    return setup_args
    

def run(setting, verbose: str=True):
    # Setup logger
    wandb_args = dict(project="lm-hpo")
    if "log_name" in setting:
        wandb_args.update(dict(name=setting["log_name"]))
    wandb.init(**wandb_args)

    # Load defaults
    model, setting = setup_model(**setting)
    # Print the number of parameters in the model
    if verbose:
        print(count_trainable_params(model)/1e6, 'M parameters')

    # Training setup
    optimizer, scheduler = setup_training(model, **setting)

    # Training model
    losses = train_and_evaluate_model(
        model=model,
        **setting,
        optimizer=optimizer,
        scheduler=scheduler,
        plot_loss=False,
        wandb_logger=wandb,
    )
    wandb.finish()
    
    # TODO: log output to return
    return 1     


if __name__ == "__main__":
    d = prepare_shakespeare()
    exp_args = exp_setup()

    from src.search_space import charLM_space_CS
    
    fixed_setting = exp_setup()
    # adding dataloader as part of experiment setup
    fixed_setting.update(dict(
        vocab_size=d["vocab_size"], 
        dataloader=lambda split, batch_size: get_batch(
            split=split, batch_size=batch_size, block_size=fixed_setting["block_size"],
            train_data=d["train_data"], valid_data=d["valid_data"], 
        )
    ))

    cs = charLM_space_CS()
    config = cs.sample_configuration()

    setting = dict()
    setting.update(dict(
        config=config.get_dictionary().copy(),
        fixed_config=fixed_setting,   # important step 
        
    ))
    print("Running an evaluation...")

    run(setting, verbose=True)
# end of file